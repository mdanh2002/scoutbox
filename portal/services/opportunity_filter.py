import json
import re
from html import unescape
from bs4 import BeautifulSoup

from portal.models import (
    Profile, PortalSettings,
    DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT,
    DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT,
)
from .ai import AIEmptyOutputWarning, effective_route_for_stage, generate_with_route, web_search_with
from .salary import normalized_pay_preferences
from .pagefetch import structured_visible_text
from .queryplanner import extract_active_cv_texts, grounded_resume_concepts, grounded_resume_roles


PURPOSES = {
    'job_opportunity', 'contract_project', 'company_hiring_signal',
    'company_outreach_target', 'editorial_seo', 'documentation',
    'directory_job_board', 'other',
}
OPPORTUNITY_PURPOSES = {'job_opportunity', 'contract_project'}
NON_OPPORTUNITY_PURPOSES = PURPOSES - OPPORTUNITY_PURPOSES
CLOUD_FILTER_PROVIDERS = {'openai', 'gemini', 'openrouter'}
MANUAL_REEVALUATION_LIMITS = {'max_input_tokens': 0, 'max_output_tokens': 4000}

CANDIDATE_EVIDENCE_RULES = (
    'Candidate evidence rules: the full active Resume text is authoritative evidence of skills and experience. '
    'Saved cv_concepts and likely_roles are editable summaries and are NOT exhaustive whitelists; never conclude that experience is absent merely because a term is missing from those summaries. '
    'High/medium/low priority text expresses preference strength, not capability. Low priority does not mean unqualified or unwanted unless the text explicitly says avoid/exclude/reject. '
    'Campaign roles/technologies explain why ScoutBox searched for the item but do not override contradictory Resume evidence. '
)


def _pct(value, default=0):
    try:
        return max(0, min(100, int(value if value is not None else default)))
    except Exception:
        return max(0, min(100, int(default or 0)))


def _optional_pct(value):
    if value in (None, ''):
        return None
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return None


def _truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y'}


def _clean_text(value, limit=1200):
    return ' '.join(str(value or '').split())[:limit]


def _web_source_rows(row, fallback=None):
    """Normalize model/meta web sources for durable manual-filter audit metadata."""
    out=[]; seen=set()
    for item in list(row.get('sources') or []) + list(fallback or []):
        if isinstance(item, dict):
            url=str(item.get('url') or item.get('source_url') or '').strip()[:1000]
            title=_clean_text(item.get('title') or item.get('label') or url, 300)
        else:
            raw=str(item or '').strip()
            url=raw[:1000] if raw.startswith(('http://','https://')) else ''
            title=_clean_text(raw,300)
        key=(url,title.casefold())
        if (url or title) and key not in seen:
            seen.add(key); out.append({'title':title or url,'url':url})
        if len(out)>=12: break
    return out


def _manual_metadata(row, research, use_web=False, include_post_age=True):
    """Return bounded manual-filter metadata; role location is available in Local or Cloud."""
    role_location={
        'location':_clean_text(row.get('role_location'),240),
        'country':_clean_text(row.get('role_country'),120),
        'confidence':_pct(row.get('role_location_confidence')),
        'reason':_clean_text(row.get('role_location_reason'),1000),
    }
    identity=row.get('identity') if isinstance(row.get('identity'),dict) else {}
    clean_identity={
        'company_name':_clean_text(identity.get('company_name') or row.get('company_name'),220),
        'company_confidence':_pct(identity.get('company_confidence') or identity.get('confidence') or row.get('company_confidence')),
        'company_reason':_clean_text(identity.get('company_reason') or identity.get('reason') or row.get('company_reason'),1000),
        'direct_role_url':str(identity.get('direct_role_url') or row.get('direct_role_url') or '').strip()[:1000],
        'same_role_confidence':_pct(identity.get('same_role_confidence') or row.get('same_role_confidence')),
        'url_reason':_clean_text(identity.get('url_reason') or row.get('direct_role_url_reason'),1200),
    }
    if not use_web:
        return {'enabled':False,'role_location':role_location,'identity':clean_identity,'company_info':{},'apply_via':{},'remote':{},'post_age':{},'sources':[]}
    company=row.get('company_info') if isinstance(row.get('company_info'),dict) else {}
    apply=row.get('apply_via') if isinstance(row.get('apply_via'),dict) else {}
    remote=row.get('remote') if isinstance(row.get('remote'),dict) else {}
    post=row.get('post_age') if include_post_age and isinstance(row.get('post_age'),dict) else {}
    sources=_web_source_rows(row,research.get('web_sources') or [])
    clean_company={
        'what_they_do':_clean_text(company.get('what_they_do'),800),'products_technology':_clean_text(company.get('products_technology'),800),
        'location':_clean_text(company.get('location'),240),'founded_year':_clean_text(company.get('founded_year'),40),
        'founded_by':_clean_text(company.get('founded_by'),500),'employee_count_or_range':_clean_text(company.get('employee_count_or_range') or company.get('company_size'),240),
        'size_structure':_clean_text(company.get('size_structure'),500),'confidence':_pct(company.get('confidence')),
    }
    clean_apply={'channel':str(apply.get('channel') or 'unknown').strip().lower()[:30],'contact_email':str(apply.get('contact_email') or '').strip()[:254],
        'application_url':str(apply.get('application_url') or apply.get('url') or '').strip()[:1000],'confidence':_pct(apply.get('confidence')),'reason':_clean_text(apply.get('reason'),1000)}
    clean_remote={'status':str(remote.get('status') or 'unknown').strip().lower()[:30],'label':_clean_text(remote.get('label'),60),
        'confidence':_pct(remote.get('confidence')),'reason':_clean_text(remote.get('reason'),1200)}
    clean_post={'posted_date':str(post.get('posted_date') or '').strip()[:80],'posted_date_explicit':_truthy(post.get('posted_date_explicit')),
        'post_age_method':str(post.get('post_age_method') or 'unknown').strip().lower()[:30],'post_age_class':str(post.get('post_age_class') or 'unknown').strip().lower()[:30],
        'post_age_confidence':_pct(post.get('post_age_confidence') or post.get('confidence')),'evergreen_confidence':_pct(post.get('evergreen_confidence')),
        'evergreen_reason':_clean_text(post.get('evergreen_reason'),1200),'post_age_reason':_clean_text(post.get('post_age_reason') or post.get('reason'),1600),
        'current_status':str(post.get('current_status') or '').strip().lower()[:40],'age_days':post.get('age_days'),
        'post_age_evidence':[x for x in (post.get('post_age_evidence') or post.get('evidence') or []) if isinstance(x,dict)][:5]}
    return {'enabled':True,'role_location':role_location,'identity':clean_identity,'company_info':clean_company,'apply_via':clean_apply,'remote':clean_remote,'post_age':clean_post,'sources':sources}


def _json_object(raw):
    text = str(raw or '').strip()
    try:
        row = json.loads(text)
        if isinstance(row, dict):
            return row
    except Exception:
        pass
    fenced = re.search(r'```\s*(?:json)?\s*([\s\S]*?)\s*```', text, re.I)
    payload = fenced.group(1).strip() if fenced else text
    a = payload.find('{')
    b = payload.rfind('}')
    if a < 0 or b <= a:
        raise ValueError('Opportunity filter model did not return a JSON object.')
    row = json.loads(payload[a:b + 1])
    if not isinstance(row, dict):
        raise ValueError('Opportunity filter model returned non-object JSON.')
    return row


def opportunity_evidence_text(opportunity):
    """Return retained target-page evidence, preferring text fetched from the role URL."""
    source = str(opportunity.description or '').strip()
    if source:
        return source, 'description'
    facts = opportunity.extracted_facts or {}
    raw = str(facts.get('description_html') or '')
    if raw:
        source = structured_visible_text(BeautifulSoup(unescape(raw),'html.parser')).strip()
        if source:
            return source, 'description_html'
    snippet = str(opportunity.raw_search_snippet or '').strip()
    if snippet:
        return snippet, 'search_snippet'
    return '', 'none'


def _clean_retained_opportunity_text(text, role='', company='', url=''):
    raw=' '.join(str(text or '').replace('\xa0',' ').split())
    if not raw:
        return ''
    raw=re.sub(r'\{\s*"(?:themeOptions|customTheme|varTheme)"\s*:\s*\{[\s\S]{0,45000}$','',raw)
    raw=re.sub(r'"[a-z0-9-]*(?:color|background|border|radius|text)[a-z0-9-]*"\s*:\s*"[^"]{0,120}"',' ',raw,flags=re.I)
    raw=re.sub(r'\b(?:primary|accent|grey|green|button|tab|navbar|card|badge|facet|entity|highlight)-[a-z0-9-]+\s*:\s*#[0-9a-f]{3,8}\b',' ',raw,flags=re.I)
    raw=' '.join(raw.split())
    anchors=[]
    if role:
        anchors.append(str(role)); anchors.append(re.split(r'\s+[|·-]\s+',str(role))[0].strip())
    if company:
        anchors.append(str(company))
    low=raw.casefold(); windows=[]
    for a in anchors:
        a=' '.join(str(a or '').split())
        if len(a)<4: continue
        pos=low.find(a.casefold())
        if pos>=0:
            windows.append(raw[max(0,pos-2000):min(len(raw),pos+7000)])
    if windows:
        return ('\n\n'.join(dict.fromkeys([raw[:1600]]+windows)))[:18000]
    return raw[:18000]


def _record_campaign_context(record=None):
    """Return campaign steering that led to a retained record, when available."""
    rows=[]; seen=set()
    if record is None:
        return rows
    candidates=[]
    try:
        origin=getattr(record,'origin_campaign',None)
        if origin is not None:
            candidates.append(origin)
    except Exception:
        pass
    try:
        manager=getattr(record,'campaigns',None)
        if manager is not None:
            candidates.extend(list(manager.all()))
    except Exception:
        pass
    for campaign in candidates:
        cid=getattr(campaign,'pk',None)
        if cid in seen:
            continue
        seen.add(cid)
        rows.append({
            'id':cid,
            'name':str(getattr(campaign,'name','') or ''),
            'roles':[x.strip() for x in re.split(r'[,;\n|]+',str(getattr(campaign,'role_families','') or '')) if x.strip()],
            'technologies':[x.strip() for x in re.split(r'[,;\n|]+',str(getattr(campaign,'technologies','') or '')) if x.strip()],
            'locations':list(getattr(campaign,'locations',None) or ([getattr(campaign,'location','')] if getattr(campaign,'location','') else [])),
            'engagement_types':[x.strip() for x in re.split(r'[,;\n|]+',str(getattr(campaign,'engagement_types','') or '')) if x.strip()],
            'company_sizes':[x.strip() for x in re.split(r'[,;\n|]+',str(getattr(campaign,'company_sizes','') or '')) if x.strip()],
            'negative_constraints':str(getattr(campaign,'negative_constraints','') or ''),
            'additional_context':str(getattr(campaign,'extra_text','') or ''),
        })
    return rows


def _candidate_scope(record=None):
    """Build the complete candidate evidence bundle for every manual re-evaluation.

    Re-evaluation must not judge fit from a compressed preference summary alone. Always
    include the saved concepts/roles, deterministic Resume vocabulary, full extracted text
    of every active Resume, and campaign steering/provenance when the record has it.
    """
    profile = Profile.objects.get_or_create(pk=1)[0]
    scope = profile.scope_json if isinstance(profile.scope_json, dict) else {}
    docs=extract_active_cv_texts()
    cv_texts=[str(x.get('text') or '') for x in docs]
    return {
        'high_priority': str(profile.high_priority_text or '')[:1800],
        'medium_priority': str(profile.medium_priority_text or '')[:1200],
        'low_priority': str(profile.low_priority_text or '')[:1000],
        'operating_location':str(profile.operating_location or ''),
        'operating_locations':list(profile.operating_locations or []),
        'cv_concepts': list(scope.get('cv_concepts') or []),
        'likely_roles': list(scope.get('likely_roles') or scope.get('roles') or scope.get('role_families') or []),
        'resume_grounded_concepts':grounded_resume_concepts(cv_texts),
        'resume_grounded_roles':grounded_resume_roles(cv_texts),
        'engagement_preferences': scope.get('engagement') or [],
        'company_size_preferences': scope.get('company_size') or [],
        'pay_preferences': normalized_pay_preferences(scope),
        'hiring_process_guidance': scope.get('interview_notes') or '',
        'preferred_languages':scope.get('preferred_languages') or [],
        'active_resumes':[
            {
                'id':d.get('id'),
                'label':d.get('label') or '',
                'name':d.get('name') or '',
                'text':str(d.get('text') or ''),
            }
            for d in docs
        ],
        'campaign_context':_record_campaign_context(record),
    }



def _cloud_policy_prompt(kind, override=''):
    text=' '.join(str(override or '').split())
    if text:
        return text[:4000]
    settings=PortalSettings.objects.get_or_create(pk=1)[0]
    if kind=='hidden_lead':
        text=' '.join(str(getattr(settings,'hidden_lead_cloud_reevaluation_prompt','') or '').split())
        return (text or DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT)[:4000]
    text=' '.join(str(getattr(settings,'opportunity_cloud_reevaluation_prompt','') or '').split())
    return (text or DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT)[:4000]


def _manual_route(provider='', model=''):
    provider = str(provider or '').strip().lower()
    model = str(model or '').strip()
    if provider and model:
        return {'provider': provider, 'model': model, 'execution_mode': 'local' if provider == 'ollama' else 'cloud'}
    route = dict(effective_route_for_stage('first_filter') or {})
    provider = str(route.get('provider') or '').strip().lower()
    model = str(route.get('model') or '').strip()
    if not provider or not model:
        raise RuntimeError('No configured first-filter AI provider/model is available.')
    return route


def _run_manual_filter(route, prompt, internet_search=False, empty_response_budget=3, budget_operation='manual', subject=None):
    provider = str(route.get('provider') or '').strip().lower()
    model = str(route.get('model') or '').strip()
    use_web = bool(internet_search and provider in CLOUD_FILTER_PROVIDERS)
    if use_web:
        # Manual Cloud+Web filtering intentionally has more headroom than routine
        # first_filter traffic: one request now returns the keep/recycle decision, Fit,
        # company information, Contact Method, Remote and (for Opportunities) Post Age.
        # Manual re-evaluation is a destructive second opinion and must carry the full
        # Candidate Profile + every active Resume. A zero input cap means ScoutBox does not
        # silently pre-trim this forensic evidence; if a selected provider/model cannot accept
        # the request, the request should fail rather than make a decision from a partial CV.
        limits=dict(MANUAL_REEVALUATION_LIMITS)
        retry_used=False
        try:
            raw, meta = web_search_with(
                provider,
                model,
                prompt,
                stage='first_filter',
                timeout=120,
                limits_override=limits,
                budget_operation=budget_operation,
                subject=subject,
            )
        except AIEmptyOutputWarning as first_exc:
            if provider!='gemini' or int(empty_response_budget or 0)<=1:
                raise
            retry_used=True
            try:
                # Gemini occasionally completes a grounded/tool request with HTTP 200 but
                # no visible final text. Retry once on the same user-selected model, using
                # minimal thinking and without forcing responseMimeType=application/json.
                # ScoutBox's JSON extraction/recovery still validates the returned object.
                raw, meta = web_search_with(
                    provider,
                    model,
                    prompt,
                    stage='first_filter',
                    timeout=120,
                    limits_override=limits,
                    budget_operation=budget_operation,
                    config_override={
                        '_manual_empty_retry_minimal':True,
                        '_manual_disable_json_mime':True,
                    },
                    subject=subject,
                )
            except AIEmptyOutputWarning as retry_exc:
                retry_exc.empty_attempts=max(2,int(getattr(first_exc,'empty_attempts',1) or 1)+int(getattr(retry_exc,'empty_attempts',1) or 1))
                retry_exc.empty_retry_attempted=True
                raise
        meta = dict(meta or {})
        return raw, {
            'internet_search': True,
            'web_sources': [dict(x) if isinstance(x,dict) else str(x) for x in (meta.get('sources') or [])[:20] if (isinstance(x,dict) or str(x or '').strip())],
            'web_queries_count': int(meta.get('queries_count') or 0),
            'empty_output_retry':retry_used,
        }
    route = dict(route)
    route['allow_internet_search'] = False
    route['fallback_allow_internet_search'] = False
    raw = generate_with_route(
        route, prompt, stage='first_filter', timeout=90, subject=subject,
        limits_override=dict(MANUAL_REEVALUATION_LIMITS),
    )
    return raw, {'internet_search': False, 'web_sources': [], 'web_queries_count': 0, 'empty_output_retry':False}


def classify_existing_opportunity(opportunity, provider='', model='', internet_search=False, empty_response_budget=3, cloud_policy_prompt=''):
    """Re-check one persisted Opportunity with an explicitly selected manual-filter model.

    With cloud web verification enabled the stored row is the anchor, but the model may
    search current public sources to verify the exact company/role/URL. Without web
    verification this remains a retained-evidence-only pass. A Cloud + Internet Search pass
    also refreshes the dense-list metadata (company info, Contact Method, remote status and post
    age) in the same grounded request so the manual second opinion is not limited to Fit.
    """
    route = _manual_route(provider, model)
    provider = str(route.get('provider') or '').strip().lower()
    model = str(route.get('model') or '').strip()
    use_web = bool(internet_search and provider in CLOUD_FILTER_PROVIDERS)
    page_text, evidence_source = opportunity_evidence_text(opportunity)
    if not use_web and (not page_text or (evidence_source == 'search_snippet' and len(page_text) < 180)):
        return {
            'decision': 'review', 'purpose': 'other', 'confidence': 0,
            'actionable': False, 'profile_relevant': True, 'relevance_confidence': 0,
            'reason': 'Not enough retained target-page text to safely re-filter this opportunity.',
            'fit_score': None, 'fit_confidence': 0,
            'fit_reason': 'Fit score was preserved because there was not enough evidence to recalculate it safely.',
            'evidence_source': evidence_source, 'provider': provider, 'model': model,
            'internet_search': False, 'web_sources': [], 'web_queries_count': 0,
        }

    verification = (
        'Internet verification is ENABLED. Treat the stored company, role and URL as the identity anchor. '
        'Search current public sources, preferring the exact target URL and official company/careers pages, to verify what the page represents now. '
        'Do not substitute a different role or company merely because it looks similar. Use web evidence to resolve missing, stale or ambiguous stored text. '
        if use_web else
        'Internet verification is DISABLED. Use only the retained ScoutBox evidence supplied below and do not assume facts that are not present. '
    )
    retained = _clean_retained_opportunity_text(page_text, opportunity.title, opportunity.company, opportunity.target_url or opportunity.url) if page_text else '(No useful retained page text; use the exact URL/company/role as the web-verification anchor.)'
    policy = _cloud_policy_prompt('opportunity', cloud_policy_prompt) if use_web else ''
    prompt = (
        'You are ScoutBox\'s manual OPPORTUNITY FILTER. Re-check one already stored row and decide whether it belongs in the Opportunities list. '
        + verification +
        (('CLOUD RE-EVALUATION INSTRUCTIONS: ' + policy + ' ') if use_web else '') +
        CANDIDATE_EVIDENCE_RULES +
        'As part of this manual second pass, independently recalculate candidate fit from 0-100 using the candidate scope and the verified/stored evidence. No previous fit score is supplied, so do not anchor on an earlier judgment. Missing compensation, company-size, engagement, or hiring-process details are neutral; known mismatches are soft signals unless they create a hard eligibility problem. Also identify the target role-specific work location from explicit role evidence. Return role_location as the specific city/region/location text (blank if unknown), role_country as one canonical country (blank if unknown), role_location_confidence (0-100), and role_location_reason. JobPosting/Job Location/Location requirements/explicit role-is-based-in evidence outranks everything else. Never use candidate operating locations, company HQ/footer office lists, related/similar jobs, or the hosting site location as the role location. Also return highlight: a natural 25-40 word technical synopsis (hard maximum 50 words) describing what the role actually involves, with concrete technologies/subsystems/responsibilities from the target role. Do not use a Role-colon-keyword format or a Technical-focus label, generic fit commentary, or a company-name repetition. Also return identity with company_name, company_confidence (0-100), and company_reason. The listing host/job board/ATS is not the employer; recover the hiring organization from explicit page evidence when possible, and leave company_name blank rather than returning BuiltIn, LinkedIn, Indeed, Himalayas or another platform. '
        + ('Because this is a Cloud Internet Search pass, ALSO find the most likely exact direct vacancy URL for this same employer and role on the employer career site or a direct ATS role page. Put it in identity.direct_role_url with identity.same_role_confidence (0-100) and identity.url_reason. Never return a generic careers homepage, search results page, aggregator listing, or merely similar vacancy. ALSO refresh current list metadata from that resolved role evidence in this same response: company_info, apply_via, remote, and post_age. company_info must contain what_they_do, products_technology, location, founded_year, founded_by, employee_count_or_range, size_structure, confidence. apply_via must contain channel (email/ats/website/public/community/unknown), contact_email, application_url, confidence, reason. remote must contain status (fully_remote/remote/hybrid/onsite/unknown), label, confidence, reason. post_age must contain posted_date (ISO date or null), posted_date_explicit, post_age_method (explicit/inferred/guess/unknown), post_age_class (normal/evergreen/unknown), post_age_confidence, evergreen_confidence, evergreen_reason, age_days, current_status, post_age_reason, post_age_evidence (up to 5 source/date/url/reason/confidence objects). A page/item updated/modified date or HTTP Last-Modified is not a posting date: never use it as posted_date or to calculate age_days; if that is the only date evidence, return posted_date=null, age_days=null and post_age_method=unknown. Relative posting phrases such as "4 months ago" are valid item-age evidence when clearly attached to this role. Return sources as a list of source objects with title and url. Do not invent missing metadata; use unknown/null and low confidence instead. ' if use_web else '') +
        'Choose purpose exactly from: job_opportunity, contract_project, company_hiring_signal, company_outreach_target, editorial_seo, documentation, directory_job_board, other. '
        'job_opportunity means one concrete current vacancy for a specific employer. contract_project means one concrete freelance/consulting/project request. '
        'company_hiring_signal and company_outreach_target are potentially useful leads but are not concrete Opportunities. editorial_seo includes articles, salary guides, job-description templates, career advice, news and SEO landing pages. documentation includes manuals, API references, tutorials and product documentation. directory_job_board means generic search/listing/aggregation pages. '
        'Do not treat a role-shaped title, responsibilities, requirements, qualifications, or generic hiring language as proof of a concrete vacancy. '
        'Also decide whether the work is genuinely relevant to the current candidate profile. The coarse relevance gate controls cleanup; fit_score is the finer ranking signal shown to the user. '
        'For cross-list correction, set convert_to_hidden_lead=true ONLY when this is clearly not a concrete vacancy/project, but the organization itself is a strong direct-outreach target with a concrete current commercial, engineering, hiring-pressure, partnership, contractor/vendor, or project signal. A generic company page, careers page, contact page, product page, article, or mere technical relevance is not enough. Set conversion_confidence 0-100 and conversion_reason. This conversion must be rare and high-confidence. '
        + ('For Cloud passes also return work_arrangement, remote_scope, candidate_geo_eligible, relocation_offered, visa_sponsorship, geo_confidence, exceptional_interest, exceptional_interest_confidence, and exceptional_interest_reason. candidate_geo_eligible=true only when the candidate can realistically work from Singapore/internationally under the verified rules. Explicit relocation or visa sponsorship is acceptable. exceptional_interest must be extremely rare: a genuinely unusual specialist role that would be regrettable to hide, not an ordinary role with matching keywords. ' if use_web else '') +
        'Return JSON only with keys: purpose, confidence (0-100), actionable (boolean), profile_relevant (boolean), relevance_confidence (0-100), reason, fit_score (0-100), fit_confidence (0-100), fit_reason, highlight, role_location, role_country, role_location_confidence, role_location_reason, identity, convert_to_hidden_lead, conversion_confidence, conversion_reason'
        + (', company_info, apply_via, remote, post_age, sources, work_arrangement, remote_scope, candidate_geo_eligible, relocation_offered, visa_sponsorship, geo_confidence, exceptional_interest, exceptional_interest_confidence, exceptional_interest_reason' if use_web else '') + '. '
        'Only set actionable=true for a concrete job_opportunity or contract_project. If evidence is ambiguous, lower confidence rather than guessing.\n\n'
        'CANDIDATE SCOPE (Candidate Profile + full active Resume evidence + campaign steering):\n' + json.dumps(_candidate_scope(opportunity), ensure_ascii=False) + '\n\n'
        f'ROLE: {opportunity.title}\nCOMPANY: {opportunity.company}\nURL: {opportunity.target_url or opportunity.url}\n\n'
        'RETAINED TARGET-PAGE TEXT:\n' + retained
    )
    raw, research = _run_manual_filter(
        route, prompt, internet_search=use_web, empty_response_budget=empty_response_budget,
        subject={'type':'opportunity','id':str(getattr(opportunity,'pk','') or ''),'label':'Manual opportunity re-evaluation'},
    )
    row = _json_object(raw)
    purpose = str(row.get('purpose') or 'other').strip().lower()
    if purpose not in PURPOSES:
        purpose = 'other'
    confidence = _pct(row.get('confidence'))
    actionable = _truthy(row.get('actionable'))
    profile_relevant = _truthy(row.get('profile_relevant'))
    relevance_confidence = _pct(row.get('relevance_confidence'), confidence)
    reason = ' '.join(str(row.get('reason') or '').split())[:1600]
    fit_score = _optional_pct(row.get('fit_score'))
    fit_confidence = _pct(row.get('fit_confidence'), relevance_confidence if fit_score is not None else 0)
    fit_reason = ' '.join(str(row.get('fit_reason') or '').split())[:1600]
    highlight = ' '.join(str(row.get('highlight') or '').split())[:600]
    convert_to_hidden_lead = _truthy(row.get('convert_to_hidden_lead'))
    conversion_confidence = _pct(row.get('conversion_confidence'))
    conversion_reason = ' '.join(str(row.get('conversion_reason') or '').split())[:1600]
    work_arrangement = _clean_text(row.get('work_arrangement'),120)
    remote_scope = _clean_text(row.get('remote_scope'),160)
    candidate_geo_eligible = _truthy(row.get('candidate_geo_eligible'))
    relocation_offered = _truthy(row.get('relocation_offered'))
    visa_sponsorship = _truthy(row.get('visa_sponsorship'))
    geo_confidence = _pct(row.get('geo_confidence'))
    exceptional_interest = _truthy(row.get('exceptional_interest'))
    exceptional_interest_confidence = _pct(row.get('exceptional_interest_confidence'))
    exceptional_interest_reason = _clean_text(row.get('exceptional_interest_reason'),1600)

    semantic_opportunity = (
        purpose in OPPORTUNITY_PURPOSES and actionable and confidence >= 65
        and profile_relevant and relevance_confidence >= 55
    )
    exceptional_keep = bool(
        use_web and exceptional_interest and exceptional_interest_confidence >= 95
        and profile_relevant and relevance_confidence >= 80 and (fit_score is None or fit_score >= 75)
    )
    if (
        convert_to_hidden_lead and purpose in {'company_hiring_signal','company_outreach_target'}
        and confidence >= 90 and conversion_confidence >= 90
        and profile_relevant and relevance_confidence >= 80 and (fit_score is None or fit_score >= 60)
    ):
        decision = 'convert_to_hidden_lead'
    elif semantic_opportunity and use_web:
        if candidate_geo_eligible or relocation_offered or visa_sponsorship:
            decision = 'keep'
        elif exceptional_keep:
            decision = 'keep'
        elif geo_confidence >= 85:
            decision = 'recycle'
        else:
            decision = 'review'
    elif semantic_opportunity:
        decision = 'keep'
    elif purpose in NON_OPPORTUNITY_PURPOSES and confidence >= 80:
        decision = 'recycle'
    elif purpose in OPPORTUNITY_PURPOSES and not actionable and confidence >= 80:
        decision = 'recycle'
    elif not profile_relevant and relevance_confidence >= 85 and confidence >= 65:
        decision = 'recycle'
    else:
        decision = 'review'

    metadata=_manual_metadata(row,research,use_web=use_web,include_post_age=True)
    return {
        'decision': decision, 'purpose': purpose, 'confidence': confidence,
        'actionable': actionable, 'profile_relevant': profile_relevant,
        'relevance_confidence': relevance_confidence,
        'reason': reason or 'No reason returned by the opportunity filter.',
        'fit_score': fit_score, 'fit_confidence': fit_confidence,
        'fit_reason': fit_reason or ('No fit reason returned by the opportunity filter.' if fit_score is not None else 'Fit score was preserved.'),
        'highlight': highlight,
        'convert_to_hidden_lead': convert_to_hidden_lead, 'conversion_confidence': conversion_confidence,
        'conversion_reason': conversion_reason,
        'work_arrangement':work_arrangement, 'remote_scope':remote_scope,
        'candidate_geo_eligible':candidate_geo_eligible, 'relocation_offered':relocation_offered,
        'visa_sponsorship':visa_sponsorship, 'geo_confidence':geo_confidence,
        'exceptional_interest':exceptional_interest, 'exceptional_interest_confidence':exceptional_interest_confidence,
        'exceptional_interest_reason':exceptional_interest_reason,
        'evidence_source': evidence_source, 'provider': provider, 'model': model,
        'metadata_refresh':metadata,
        **research,
    }


def hidden_lead_evidence_text(lead):
    """Return retained evidence suitable for re-checking one Hidden Lead."""
    evidence = str(getattr(lead, 'evidence', '') or '').strip()
    summary = str(getattr(lead, 'summary', '') or '').strip()
    match = str(getattr(lead, 'match_summary', '') or '').strip()
    if evidence:
        extras = []
        if summary:
            extras.append('SCOUTBOX SUMMARY: ' + summary)
        if match:
            extras.append('MATCH TERMS: ' + match)
        return '\n\n'.join([evidence] + extras), 'evidence'
    fallback = '\n\n'.join(x for x in [summary, match] if x)
    if fallback:
        return fallback, 'summary'
    return '', 'none'


def classify_existing_hidden_lead(lead, provider='', model='', internet_search=False, empty_response_budget=3, cloud_policy_prompt=''):
    """Re-check one persisted Hidden Lead with the selected manual-filter model."""
    route = _manual_route(provider, model)
    provider = str(route.get('provider') or '').strip().lower()
    model = str(route.get('model') or '').strip()
    use_web = bool(internet_search and provider in CLOUD_FILTER_PROVIDERS)
    page_text, evidence_source = hidden_lead_evidence_text(lead)
    if not use_web and (not page_text or len(page_text) < 180):
        return {
            'decision': 'review', 'purpose': 'other', 'confidence': 0,
            'actionable': False, 'profile_relevant': True, 'relevance_confidence': 0,
            'reason': 'Not enough retained company/page evidence to safely re-filter this Hidden Lead.',
            'fit_score': None, 'fit_confidence': 0,
            'fit_reason': 'Fit score was preserved because there was not enough evidence to recalculate it safely.',
            'evidence_source': evidence_source, 'provider': provider, 'model': model,
            'internet_search': False, 'web_sources': [], 'web_queries_count': 0,
        }

    verification = (
        'Internet verification is ENABLED. Treat the stored company and URL as the identity anchor. '
        'Search current public sources, preferring the exact target URL and official company/project pages, to verify whether this is a real and relevant outreach target now. '
        'Do not replace it with another company or unrelated job result. Use the web to recover context when ScoutBox retained only a weak snippet. '
        if use_web else
        'Internet verification is DISABLED. Use only the retained ScoutBox evidence below and do not assume missing facts. '
    )
    retained = _clean_retained_opportunity_text(page_text, '', lead.company, lead.target_url or lead.source_url) if page_text else '(No useful retained text; use the exact company and URL as the web-verification anchor.)'
    policy = _cloud_policy_prompt('hidden_lead', cloud_policy_prompt) if use_web else ''
    prompt = (
        'You are ScoutBox\'s manual HIDDEN LEAD FILTER. Re-check one already stored Hidden Lead. '
        + verification +
        (('CLOUD RE-EVALUATION INSTRUCTIONS: ' + policy + ' ') if use_web else '') +
        CANDIDATE_EVIDENCE_RULES +
        'A Hidden Lead is a real company, engineering team, consultancy, product/project organization, or other plausible direct outreach target that shows concrete technical activity relevant to the candidate, even when no job is advertised. '
        'Hidden Leads are NOT generic job boards, articles, news/editorial pages, documentation/tutorial pages, forums/publishers, search platforms, or unrelated companies. '
        'Choose purpose exactly from: job_opportunity, contract_project, company_hiring_signal, company_outreach_target, editorial_seo, documentation, directory_job_board, other. '
        'company_outreach_target means the evidence shows the organization itself building/providing relevant technical products, systems, engineering, consulting, or project work and it is plausible to contact them directly. '
        'company_hiring_signal means there is a useful company-level hiring/collaboration signal but not one concrete vacancy. '
        'A concrete job_opportunity or contract_project is valuable but belongs in Opportunities, so identify it accurately rather than calling it noise. '
        'For cross-list correction, set convert_to_opportunity=true ONLY when the evidence clearly proves one specific current vacancy or one specific contract/project request. Return conversion_title, conversion_url (the exact role/project URL, never a generic careers/search page), conversion_company, conversion_exact_vacancy, conversion_confidence (0-100), and conversion_reason. This conversion must be rare and high-confidence; ambiguous hiring signals stay as Hidden Leads. '
        'Also decide whether the organization/work is genuinely relevant to the current candidate profile. Independently recalculate fit_score from 0-100 for how worthwhile this organization/work is as a direct outreach target for the candidate. No previous score is supplied, so do not anchor on an earlier judgment. Missing pay/company-size/engagement/hiring-process details are neutral; known mismatches are soft signals unless they create a hard eligibility problem. '
        + ('Because this is a Cloud Internet Search pass, ALSO assess company_scale (micro/small/medium/large/unknown), direct_decision_maker_access, need_signal, need_signal_type, need_signal_confidence, need_signal_evidence, buyer_direction (may_buy_from_candidate/sells_to_candidate/neutral/unclear), exceptional_interest, exceptional_interest_confidence, exceptional_interest_reason, and exceptional_interest_specificity. A contact page, sales page, relevant technology, or the fact that the company sells engineering services is not a buyer signal. exceptional_interest is a very rare escape hatch only for a concrete unusual activity/problem (for example obsolete-media recovery or rebuilding an abandoned legacy system), never a keyword mention such as IDE/SCSI/firmware. ALSO refresh current company/outreach metadata in the same grounded response: company_info (what_they_do, products_technology, location, founded_year, founded_by, employee_count_or_range, size_structure, confidence), apply_via (channel=email/website/public/community/unknown, contact_email, application_url as the best direct contact page, confidence, reason), and remote (fully_remote/remote/hybrid/onsite/unknown plus label, confidence, reason) when public evidence supports it. Return sources as title/url objects. Hidden Leads have no job-post age field, so do not invent a posting date for a company-level lead. ' if use_web else '') +
        'Return JSON only with keys: purpose, confidence (0-100), actionable (boolean), profile_relevant (boolean), relevance_confidence (0-100), reason, fit_score (0-100), fit_confidence (0-100), fit_reason, convert_to_opportunity, conversion_exact_vacancy, conversion_confidence, conversion_reason, conversion_title, conversion_url, conversion_company'
        + (', company_info, apply_via, remote, sources, company_scale, direct_decision_maker_access, need_signal, need_signal_type, need_signal_confidence, need_signal_evidence, buyer_direction, exceptional_interest, exceptional_interest_confidence, exceptional_interest_reason, exceptional_interest_specificity' if use_web else '') + '. '
        'For Hidden Leads, actionable=true means the page provides enough evidence that direct outreach/collaboration could reasonably be worthwhile; it does not require a posted vacancy. '
        'If evidence is ambiguous, lower confidence rather than guessing.\n\n'
        'CANDIDATE SCOPE (Candidate Profile + full active Resume evidence + campaign steering):\n' + json.dumps(_candidate_scope(lead), ensure_ascii=False) + '\n\n'
        f'COMPANY: {lead.company}\nURL: {lead.target_url or lead.source_url}\n\n'
        'RETAINED COMPANY/PAGE EVIDENCE:\n' + retained
    )
    raw, research = _run_manual_filter(
        route, prompt, internet_search=use_web, empty_response_budget=empty_response_budget,
        subject={'type':'hidden_lead','id':str(getattr(lead,'pk','') or ''),'label':'Manual Hidden Lead re-evaluation'},
    )
    row = _json_object(raw)
    purpose = str(row.get('purpose') or 'other').strip().lower()
    if purpose not in PURPOSES:
        purpose = 'other'
    confidence = _pct(row.get('confidence'))
    actionable = _truthy(row.get('actionable'))
    profile_relevant = _truthy(row.get('profile_relevant'))
    relevance_confidence = _pct(row.get('relevance_confidence'), confidence)
    reason = ' '.join(str(row.get('reason') or '').split())[:1600]
    fit_score = _optional_pct(row.get('fit_score'))
    fit_confidence = _pct(row.get('fit_confidence'), relevance_confidence if fit_score is not None else 0)
    fit_reason = ' '.join(str(row.get('fit_reason') or '').split())[:1600]
    convert_to_opportunity = _truthy(row.get('convert_to_opportunity'))
    conversion_exact_vacancy = _truthy(row.get('conversion_exact_vacancy'))
    conversion_confidence = _pct(row.get('conversion_confidence'))
    conversion_reason = ' '.join(str(row.get('conversion_reason') or '').split())[:1600]
    conversion_title = ' '.join(str(row.get('conversion_title') or '').split())[:300]
    conversion_url = str(row.get('conversion_url') or '').strip()[:1000]
    conversion_company = ' '.join(str(row.get('conversion_company') or '').split())[:220]
    company_scale = str(row.get('company_scale') or 'unknown').strip().lower()[:30]
    direct_decision_maker_access = _truthy(row.get('direct_decision_maker_access'))
    need_signal = _truthy(row.get('need_signal'))
    need_signal_type = _clean_text(row.get('need_signal_type'),160)
    need_signal_confidence = _pct(row.get('need_signal_confidence'))
    need_signal_evidence = _clean_text(row.get('need_signal_evidence'),1600)
    buyer_direction = str(row.get('buyer_direction') or 'unclear').strip().lower()[:40]
    exceptional_interest = _truthy(row.get('exceptional_interest'))
    exceptional_interest_confidence = _pct(row.get('exceptional_interest_confidence'))
    exceptional_interest_reason = _clean_text(row.get('exceptional_interest_reason'),1600)
    exceptional_interest_specificity = _clean_text(row.get('exceptional_interest_specificity'),1000)

    hidden_lead_purposes = {'company_hiring_signal', 'company_outreach_target'}
    noise_purposes = {'editorial_seo', 'documentation', 'directory_job_board', 'other'}
    if (
        convert_to_opportunity and conversion_exact_vacancy and purpose in OPPORTUNITY_PURPOSES and actionable
        and confidence >= 92 and conversion_confidence >= 92
        and profile_relevant and relevance_confidence >= 80 and bool(conversion_title)
        and conversion_url.startswith(('http://', 'https://'))
    ):
        decision = 'convert_to_opportunity'
    elif use_web:
        approachable = direct_decision_maker_access or company_scale in {'micro','small'}
        strong_need = bool(
            purpose in hidden_lead_purposes and need_signal and need_signal_confidence >= 80
            and buyer_direction == 'may_buy_from_candidate'
            and profile_relevant and relevance_confidence >= 65
            and (approachable or need_signal_confidence >= 90)
        )
        exceptional_keep = bool(
            purpose not in {'editorial_seo','documentation','directory_job_board'} and exceptional_interest
            and exceptional_interest_confidence >= 95
            and profile_relevant and relevance_confidence >= 80
            and bool(exceptional_interest_specificity or exceptional_interest_reason)
        )
        if strong_need or exceptional_keep:
            decision = 'keep'
        elif purpose in noise_purposes and confidence >= 80:
            decision = 'recycle'
        elif purpose in hidden_lead_purposes and need_signal_confidence >= 80 and not need_signal and not exceptional_keep:
            decision = 'recycle'
        elif purpose in hidden_lead_purposes and buyer_direction in {'sells_to_candidate','neutral'} and confidence >= 80 and not exceptional_keep:
            decision = 'recycle'
        elif not profile_relevant and relevance_confidence >= 85 and confidence >= 65:
            decision = 'recycle'
        else:
            decision = 'review'
    elif (
        purpose in hidden_lead_purposes and actionable and confidence >= 65
        and profile_relevant and relevance_confidence >= 55
    ):
        decision = 'keep'
    elif purpose in noise_purposes and confidence >= 80:
        decision = 'recycle'
    elif purpose in hidden_lead_purposes and not actionable and confidence >= 85:
        decision = 'recycle'
    elif not profile_relevant and relevance_confidence >= 85 and confidence >= 65:
        decision = 'recycle'
    else:
        decision = 'review'

    metadata=_manual_metadata(row,research,use_web=use_web,include_post_age=False)
    return {
        'decision': decision, 'purpose': purpose, 'confidence': confidence,
        'actionable': actionable, 'profile_relevant': profile_relevant,
        'relevance_confidence': relevance_confidence,
        'reason': reason or 'No reason returned by the Hidden Lead filter.',
        'fit_score': fit_score, 'fit_confidence': fit_confidence,
        'fit_reason': fit_reason or ('No fit reason returned by the Hidden Lead filter.' if fit_score is not None else 'Fit score was preserved.'),
        'convert_to_opportunity': convert_to_opportunity, 'conversion_exact_vacancy': conversion_exact_vacancy,
        'conversion_confidence': conversion_confidence, 'conversion_reason': conversion_reason,
        'conversion_title': conversion_title, 'conversion_url': conversion_url, 'conversion_company': conversion_company,
        'company_scale':company_scale, 'direct_decision_maker_access':direct_decision_maker_access,
        'need_signal':need_signal, 'need_signal_type':need_signal_type, 'need_signal_confidence':need_signal_confidence,
        'need_signal_evidence':need_signal_evidence, 'buyer_direction':buyer_direction,
        'exceptional_interest':exceptional_interest, 'exceptional_interest_confidence':exceptional_interest_confidence,
        'exceptional_interest_reason':exceptional_interest_reason, 'exceptional_interest_specificity':exceptional_interest_specificity,
        'evidence_source': evidence_source, 'provider': provider, 'model': model,
        'metadata_refresh':metadata,
        **research,
    }

def contact_evidence_text(contact):
    """Retained Address Book evidence for a manual second opinion."""
    pieces=[]
    if str(getattr(contact,'company_summary','') or '').strip():
        pieces.append('COMPANY SUMMARY: '+str(contact.company_summary).strip())
    intel=getattr(contact,'company_intel',{}) or {}
    if isinstance(intel,dict):
        for row in intel.get('facts') or []:
            if isinstance(row,dict) and (row.get('label') or row.get('value')):
                pieces.append(f"{row.get('label') or 'Company fact'}: {row.get('value') or ''}")
    if str(getattr(contact,'notes','') or '').strip():
        pieces.append('NOTES: '+str(contact.notes).strip())
    text='\n'.join(pieces)
    return text, ('company_context' if text else 'none')


def classify_existing_contact(contact, provider='', model='', internet_search=False, empty_response_budget=3, budget_operation='manual'):
    """Re-evaluate whether an Address Book contact is worth retaining/contacting for the candidate."""
    route=_manual_route(provider,model)
    provider=str(route.get('provider') or '').strip().lower()
    model=str(route.get('model') or '').strip()
    use_web=bool(internet_search and provider in CLOUD_FILTER_PROVIDERS)
    retained,evidence_source=contact_evidence_text(contact)
    limited_local=not use_web and len(retained)<80
    verification=(
        'Internet verification is ENABLED. Treat the stored company, contact email and source URL as the identity anchor. Search current public sources for the exact company and its technical work. Do not invent a different person or email. '
        if use_web else
        ('Internet verification is DISABLED and retained evidence is limited. Use the stored company/contact identity plus candidate scope, score conservatively, and lower fit_confidence when evidence is weak. Do not invent specific company facts. '
         if limited_local else 'Internet verification is DISABLED. Use only the retained ScoutBox evidence below. ')
    )
    prompt=(
        "You are ScoutBox's manual ADDRESS BOOK RE-EVALUATION. Decide how worthwhile this stored contact is for direct networking, opportunity discovery, collaboration or lead outreach for the saved candidate profile. "
        +verification+
        CANDIDATE_EVIDENCE_RULES+
        'The stored email is already the contact method; do not derive or replace it. Independently calculate fit_score from 0-100 based on the company/team technical relevance and usefulness of this contact. No previous Fit score is supplied. '
        'Choose purpose exactly from: company_outreach_target, company_hiring_signal, job_opportunity, contract_project, editorial_seo, documentation, directory_job_board, other. '
        'actionable=true means the stored contact is a plausible person/shared recruiting/business/engineering route for useful outreach. A generic but legitimate jobs/recruiting/contact inbox can still be actionable. Administrative/privacy/compliance-only addresses are not actionable. '
        +('Because this is a Cloud Internet Search pass, also refresh company_info with what_they_do, products_technology, location, founded_year, founded_by, employee_count_or_range, size_structure, confidence; return sources as title/url objects. Do not invent missing facts. ' if use_web else '')+
        'Return JSON only with keys: purpose, confidence (0-100), actionable (boolean), profile_relevant (boolean), relevance_confidence (0-100), reason, fit_score (0-100), fit_confidence (0-100), fit_reason'
        +(', company_info, sources' if use_web else '')+'. '
        'Recycle only when the contact/company is clearly unrelated or the address is clearly not a useful outreach contact. If uncertain, choose review.\n\n'
        'CANDIDATE SCOPE (Candidate Profile + full active Resume evidence):\n'+json.dumps(_candidate_scope(contact),ensure_ascii=False)+'\n\n'
        f'CONTACT: {getattr(contact,"name","") or "Shared contact"}\nCOMPANY: {getattr(contact,"company","")}\nROLE: {getattr(contact,"title","")}\nEMAIL: {getattr(contact,"email","")}\nCOUNTRY: {getattr(contact,"company_country","")}\nSOURCE URL: {getattr(contact,"source_url","")}\n\n'
        'RETAINED ADDRESS BOOK EVIDENCE:\n'+(retained[:18000] if retained else '(No retained company summary; use the identity anchor for web verification.)')
    )
    raw,research=_run_manual_filter(
        route,prompt,internet_search=use_web,empty_response_budget=empty_response_budget,
        budget_operation=budget_operation,
        subject={'type':'contact','id':str(getattr(contact,'pk','') or ''),'label':'Manual Address Book re-evaluation'},
    )
    row=_json_object(raw)
    purpose=str(row.get('purpose') or 'company_outreach_target').strip().lower()
    if purpose not in PURPOSES: purpose='other'
    confidence=_pct(row.get('confidence'))
    actionable=_truthy(row.get('actionable'))
    profile_relevant=_truthy(row.get('profile_relevant'))
    relevance_confidence=_pct(row.get('relevance_confidence'),confidence)
    reason=' '.join(str(row.get('reason') or '').split())[:1600]
    fit_score=_optional_pct(row.get('fit_score'))
    fit_confidence=_pct(row.get('fit_confidence'),relevance_confidence if fit_score is not None else 0)
    fit_reason=' '.join(str(row.get('fit_reason') or '').split())[:1600]
    if actionable and profile_relevant and confidence>=60 and relevance_confidence>=50:
        decision='keep'
    elif (not actionable and confidence>=90) or (not profile_relevant and relevance_confidence>=90 and confidence>=70):
        decision='recycle'
    else:
        decision='review'
    metadata=_manual_metadata(row,research,use_web=use_web,include_post_age=False)
    return {
        'decision':decision,'purpose':purpose,'confidence':confidence,'actionable':actionable,
        'profile_relevant':profile_relevant,'relevance_confidence':relevance_confidence,
        'reason':reason or 'No reason returned by the Address Book re-evaluation.',
        'fit_score':fit_score,'fit_confidence':fit_confidence,
        'fit_reason':fit_reason or ('No fit reason returned.' if fit_score is not None else 'Fit score was preserved.'),
        'evidence_source':evidence_source,'provider':provider,'model':model,'metadata_refresh':metadata,**research,
    }

