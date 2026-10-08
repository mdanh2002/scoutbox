import json
import os
import re
import time
import urllib.parse
import threading
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from django.utils import timezone
from django.db.models import Q
from django.db import close_old_connections
from portal.models import Campaign, Opportunity, SearchProviderStat, PortalSettings, SearchSource, Application, OpportunityEvidence, FacebookConfig, UsageMetric, BackgroundJob, Profile, CompanyLead
from .search import choose_providers, provider_selection_details, provider_query_allowance, provider_budget_remaining, provider_market_compatible, provider_is_usable, build_campaign_query_plan, search_source, facebook_index_queries, facebook_graph_posts, remember_facebook_page, revalidate_facebook_pages, unwrap_search_result_url, is_search_engine_url, search_title_contaminated, searchapi_research
from .queryplanner import pre_score_hit, grounded_profile_relevance, build_search_profile, _role_alias_fallback
from .freshness import recompute, apply_cloud_post_age
from .enrichment import enrich
from .ai import route_for_stage, effective_cloud_bundle_anchor, cloud_discovery_route, effective_route_for_stage, generate_with, generate_with_route, has_usable_cloud_web_model, LocalAILaneBusy
from .cloud_budget import is_cloud_provider, usage_context
from .ai_lifecycle import reserve_attempt
from .cloud_discovery import discover as cloud_discover, research_candidate, research_hiring_signal, persist_cloud_contacts, persist_cloud_hidden_leads
from .presentation import clean_placeholder
from .blacklist import is_blacklisted_url
from .platforms import is_job_board_host, is_job_platform_host, is_platform_company_name, is_plausible_company_name, company_from_ats_url
from .pagefetch import fetch_target, primarily_english
from .content_quality import sanitize_mixed_script_title, normalize_opportunity_title, normalize_remote_constraints, remote_work_evidence, work_arrangement_evidence, soft_missing_reason, explicit_post_date_signal, extract_role_location, adult_content_reason
from .role_gate import classify_role_page
from .opportunity_urls import looks_like_specific_opportunity_url, is_disallowed_adult_url
from .languages import preferred_language_delta
from .mailbox import assignable_contact_email, clean_contact_email, find_automatic_contact_email, promote_record_contact_to_addressbook
from .cold import company_from_page, display_company_name, infer_country, is_documentation_like, is_general_market_company, is_general_market_host, preliminary_company_summary, registrable_domain, recycled_lead_match, hidden_lead_minibrowser_admission, strip_hidden_lead_evidence_markers
from .dedup import active_duplicate_opportunity, active_role_family_duplicate, company_concentration_decision, vacancy_url_key, active_opportunity_for_company, suppress_overlapping_leads
from .highlights import derive_opportunity_highlight, opportunity_specific_highlight
from .salary import salary_from_cloud_result, salary_from_retained_opportunity, apply_salary_info, parse_salary_text
from .company_research import enrich_company_intel_from_retained
from .campaign_links import attribute_campaign
from .fresh_sources import direct_source_rows, forum_source_rows, non_forum_direct_source_rows
from .location import resolve_opportunity_location
from .source_domains import expand_source_domains
from .location_values import normalize_location_items
from .selectivity import current as selectivity_current, opportunity_thresholds, lead_policy, specialist_alignment, campaign_alignment, instruction as selectivity_instruction
from .discovery_markets import market_plan, market_query, market_search_meta, market_from_location, auto_multilingual_languages, multilingual_assignments, MARKET_BY_CODE


def canonical(url):
    try:
        p=urllib.parse.urlsplit(url); q=urllib.parse.parse_qsl(p.query,keep_blank_values=True)
        q=[x for x in q if not x[0].lower().startswith(('utm_','ref','trk','tracking','source'))]
        return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),urllib.parse.urlencode(q),''))
    except Exception: return url



class CampaignStopped(RuntimeError):
    pass


class CloudWebUnavailable(RuntimeError):
    pass


def _cloud_recommendation_status(result):
    rec=' '.join(str(result.get('recommendation') or '').split()).strip().casefold()
    if rec in {'apply now','apply','high priority'}:
        return 'apply'
    if rec in {'review','consider','review soon'}:
        return 'review'
    if rec in {'information only','info','informational'}:
        return 'info'
    try:
        fit=int(result.get('_pre_score') if result.get('_pre_score') is not None else result.get('fit_score') or 0)
    except Exception:
        fit=0
    # Preserve useful niche results even when the model omitted recommendation.
    if fit >= 82:
        return 'apply'
    if fit >= 58:
        return 'review'
    return 'info'



def _deterministic_company_from_evidence(*values):
    """Recover an employer from strong visible aggregator/page wording without AI."""
    texts=[' '.join(str(v or '').split()) for v in values if str(v or '').strip()]
    patterns=(
        r'\bAbout the Role\s+([A-Z][A-Za-z0-9&.+\'’\- ]{1,70}?)(?=\s+(?:is|seeks|builds|provides|develops|offers|\||[-–—])|[.,;:]|$)',
        r'\b([A-Z][A-Za-z0-9&.+\'’\- ]{1,70}?)\s+(?:is|are)\s+(?:hiring|seeking|looking for|recruiting)\b',
        r'\b(?:at|for)\s+([A-Z][A-Za-z0-9&.+\'’\- ]{1,70}?)\s+(?:we|you|the role|is hiring|is seeking)\b',
    )
    for text in texts:
        for pattern in patterns:
            match=re.search(pattern,text)
            if not match:
                continue
            candidate=' '.join(match.group(1).split()).strip(' -–—|:;,')[:160]
            if is_plausible_company_name(candidate):
                return candidate
    return ''

def _company_country_value(value):
    text=' '.join(str(value or '').split()).strip()[:120]
    low=text.casefold()
    if not text or 'remote' in low or low in {'worldwide','global','anywhere','distributed'} or 'home based' in low or 'home-based' in low:
        return ''
    return text


def _opportunity_country_from_page(target_url, inspected, page_title='', page_text='', ai_country=''):
    """Choose the role location country from the strongest page evidence available."""
    inspected=inspected or {}
    structured=infer_country(target_url,'',location_hint=inspected.get('jobposting_location') or '')
    if structured:
        return structured
    # infer_country gives labelled job-location and US city/state evidence priority over
    # arbitrary country names in navigation/footer text.
    visible=infer_country(target_url,(str(page_title or '')+' '+str(page_text or '')).strip(),strict=True)
    if visible:
        return visible
    # Bare model-supplied country guesses are not evidence. Candidate/profile geography
    # previously leaked through this fallback and mislabeled unrelated jobs.
    return ''


class SearchProvidersUnavailable(RuntimeError):
    def __init__(self, stopped_reason, message, provider_selection=None):
        self.stopped_reason=stopped_reason
        self.provider_selection=provider_selection or {}
        super().__init__(message)


def _progress(callback, value, message):
    if callback:
        try: callback(value, message)
        except Exception: pass

def _check_stop(callback):
    if callback and callback():
        raise CampaignStopped('Campaign stopped by user')


_LOCAL_PAGE_PURPOSES={'job_opportunity','contract_project','company_hiring_signal','company_outreach_target','editorial_seo','documentation','directory_job_board','other'}
_LOCAL_REMOTE_STATES={'fully_remote','remote','hybrid','onsite','unknown'}
_LOCAL_APPLY_SIGNALS=(
    'apply now','apply for this job','submit application','submit your application','apply for this role',
    'send your cv','send your resume','we are hiring',"we're hiring",'now hiring','join our team',
    'we are looking for',"we're looking for",'we are seeking',"we're seeking",'applications close',
)
_LOCAL_JOB_PATHS=('/jobs/','/job/','/careers/','/career/','/vacancy/','/vacancies/','/positions/','/position/')
_ROLE_WORDS=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')
_LOCAL_ATS_HOSTS=('greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com','jobvite.com','icims.com','bamboohr.com')


def _search_engine_unavailable_error(provider_selection):
    exhausted=(provider_selection or {}).get('budget_exhausted') or []
    usable=int((provider_selection or {}).get('usable_count') or 0)
    if usable and exhausted:
        return 'Search engine discovery unavailable: configured provider daily budgets are exhausted.'
    return 'Search engine discovery unavailable: no eligible search provider is configured.'


def _record_search_engine_unavailable(message):
    try:
        UsageMetric.objects.create(category='search',provider='Search engines',stage='query',requests=0,pages=0,errors=1,metadata={'error':str(message or '')[:500],'reason':'search_engine_unavailable'})
    except Exception:
        pass



def _direct_source_search_queries(campaign, direct_meta, search_profile=None):
    """Build mandatory Local Discovery site: fallbacks for direct-capable sources.

    Search-engine fallback must not inherit the bounded direct-adapter selection.  It uses
    the full adapter-capable source pool (including credentialed adapters that cannot run)
    and schedules one domain variant per source before any source receives a second variant.
    """
    names=[str(x) for x in ((direct_meta or {}).get('search_fallback_sources') or (direct_meta or {}).get('available_sources') or (direct_meta or {}).get('sources') or []) if str(x).strip()]
    if not names: return []
    anchor=''
    for piece in re.split(r'[,;|\n]+',str(getattr(campaign,'role_families','') or '')):
        if 3<=len(piece.strip())<=80: anchor=piece.strip(); break
    if not anchor:
        skills=(search_profile or {}).get('skills') or []
        if skills:
            first=skills[0]; anchor=str(first.get('term') if isinstance(first,dict) else first).strip()
    anchor=anchor or 'hiring'
    out=[]; max_queries=48
    sources=list(SearchSource.objects.filter(enabled=True,name__in=names).exclude(base_url='').order_by('-priority','category','name'))
    if not sources:
        return out
    # One source slot first, one domain-family variant second. Advancing by max_queries
    # gives bounded coverage even if the adapter-capable pool eventually grows beyond 48.
    bucket=int(timezone.now().timestamp()//(2*60*60))+int(getattr(campaign,'pk',0) or 0)
    start=(bucket*max_queries)%len(sources)
    ordered=sources[start:]+sources[:start]
    for source_index,source in enumerate(ordered[:max_queries]):
        try: domain=(urllib.parse.urlsplit(source.base_url).hostname or '').lower().removeprefix('www.')
        except Exception: domain=''
        if not domain: continue
        variants=expand_source_domains(domain,limit=6) or [domain]
        expanded_domain=variants[(bucket+source_index)%len(variants)]
        source_type=str(getattr(source,'source_type','') or '').lower()
        if source_type=='forum':
            # Forum adapters browse listings natively; one concise fallback phrase per source
            # is enough here because Forums has a separate dedicated discovery lane.
            phrase=('paid help','paid project','contractor')[(bucket+source_index)%3]
            quoted=f'"{phrase}"' if ' ' in phrase else phrase
            out.append({'source_name':source.name,'domain':expanded_domain,'query':f'site:{expanded_domain} {quoted}'})
        else:
            phrase=anchor.replace('"',' ').strip()
            out.append({'source_name':source.name,'domain':expanded_domain,'query':f'site:{expanded_domain} "{phrase}"'})
    return out[:max_queries]


def _required_direct_source_search_records(provider, required_queries, cfg, *, test=False, progress_callback=None, should_stop=None, progress_base=20):
    """Guarantee Local Discovery search-engine coverage for direct-capable source domains."""
    records=[]; errors=[]; requests=0; satisfied=[]
    if not provider: return records,errors,{'provider':'','requests':0,'raw_results':0,'sources':[]}
    consecutive_errors=0; error_limit=_search_provider_error_limit()
    for idx,item in enumerate(required_queries or [],1):
        _check_stop(should_stop)
        q=str(item.get('query') or '').strip()
        if not q: continue
        value=min(44,progress_base+int(10*idx/max(1,len(required_queries))))
        msg=f'Parallel search fallback {provider.name}: {item.get("source_name") or item.get("domain")}'
        _progress(progress_callback,value,msg)
        market_info=item.get('market') or {}; market=MARKET_BY_CODE.get(str(market_info.get('market_code') or ''))
        results,err=_search_source_with_liveness(provider,q,3 if test else min(10,int(cfg.max_results_per_query or 10)),progress_callback,value,msg,should_stop,market=market)
        requests+=1
        if err:
            consecutive_errors+=1
            errors.append(f'{provider.name}/{item.get("source_name") or item.get("domain")}: {err}')
            if consecutive_errors>=error_limit:
                errors.append(f'{provider.name}: parallel direct-source fallback stopped after {consecutive_errors} consecutive request errors; remaining sources will rotate into later runs.')
                break
            continue
        consecutive_errors=0
        satisfied.append(item.get('source_name') or item.get('domain'))
        for row in results or []:
            result=dict(row or {})
            result['_acquisition_path']='Search engine discovery'
            if item.get('market'):
                result['_discovery_market']=(item.get('market') or {}).get('market',''); result['_discovery_market_code']=(item.get('market') or {}).get('market_code','')
                # A local-board search (for example hk.jobsdb.com or seek.com.au) is
                # bounded market evidence. Keep it separate from provider locale so it
                # can resolve an otherwise ambiguous role without becoming a global
                # country default. Explicit role/structured locations still win later.
                result['_market_location_hint']=(item.get('market') or {}).get('market','')
            result['_provenance']=[{'source':provider.name,'query':q,'url':result.get('url',''),'acquisition_path':'Search engine discovery','parallel_direct_source':item.get('source_name','')}]
            records.append({'result':result,'source':provider,'query':q})
    return records,errors,{'provider':provider.name,'requests':requests,'raw_results':len(records),'sources':satisfied,'queries':[x.get('query') for x in (required_queries or [])]}


def _model_json_object(raw):
    text=str(raw or '').strip()
    fenced=re.search(r'```\s*(?:json)?\s*([\s\S]*?)\s*```',text,re.I)
    payload=fenced.group(1).strip() if fenced else text
    a=payload.find('{'); b=payload.rfind('}')
    if a<0 or b<=a:
        raise ValueError('Local qualification model did not return JSON.')
    row=json.loads(payload[a:b+1])
    if not isinstance(row,dict):
        raise ValueError('Local qualification model returned a non-object JSON value.')
    return row


def _local_action_signals(url, text, *, has_jobposting_schema=False):
    """Local-only structural evidence that a page is a concrete opening.

    Deliberately excludes generic phrases such as "job description", responsibilities,
    requirements and qualifications because SEO/job-template pages routinely contain them.
    """
    parts=urllib.parse.urlsplit(url or '')
    host=(parts.hostname or '').lower(); path=(parts.path or '').lower()
    sample=' '.join(str(text or '').lower().split())[:24000]
    signals=[]
    if has_jobposting_schema: signals.append('JobPosting structured data')
    if any(host==h or host.endswith('.'+h) for h in _LOCAL_ATS_HOSTS): signals.append('recognized ATS host')
    if any(bit in path for bit in _LOCAL_JOB_PATHS): signals.append('job/career item URL')
    actions=[phrase for phrase in _LOCAL_APPLY_SIGNALS if phrase in sample]
    if actions: signals.extend(actions[:3])
    return {'clear':bool(has_jobposting_schema or any('ATS' in x for x in signals) or any('item URL' in x for x in signals) or actions),'signals':signals[:8]}


def _local_profile_scope(campaign, grounded):
    profile=Profile.objects.get_or_create(pk=1)[0]
    return {
        'campaign_roles':str(getattr(campaign,'role_families','') or '')[:1200],
        'campaign_technologies':str(getattr(campaign,'technologies','') or '')[:1200],
        'campaign_notes':str(getattr(campaign,'extra_text','') or '')[:900],
        'grounded_matches':list((grounded or {}).get('matches') or [])[:12],
        'title_matches':list((grounded or {}).get('title_matches') or [])[:8],
        'high_priority':str(profile.high_priority_text or '')[:1000],
        'medium_priority':str(profile.medium_priority_text or '')[:700],
    }


def _local_page_review(campaign, title, company, url, page_text, role_gate, grounded, *, has_jobposting_schema=False):
    """Local Ollama semantic gate used only by Local AI Discovery before persistence."""
    route=effective_route_for_stage('first_filter',discovery_mode='source_guided') or {}
    if str(route.get('provider') or '').lower()!='ollama' or not str(route.get('model') or '').strip():
        raise RuntimeError('Local pre-persistence qualification requires an enabled Ollama model.')
    structural=_local_action_signals(url,page_text,has_jobposting_schema=has_jobposting_schema)
    prompt=(
        'You are the final PRE-PERSISTENCE quality gate for ScoutBox Local AI Discovery. Classify the PURPOSE of one fetched web page using its actual page text, not search-query wording. '
        'A page can be technically relevant and still be the wrong record type. Choose purpose exactly from: job_opportunity, contract_project, company_hiring_signal, company_outreach_target, editorial_seo, documentation, directory_job_board, other. '
        'job_opportunity means one concrete current vacancy for a specific employer. contract_project means one concrete freelance/consulting/project request. '
        'company_hiring_signal means the organization appears relevant and hiring but this page is not a concrete single opening. company_outreach_target means the organization itself plausibly buys/needs the candidate\'s work and is sensible to contact directly, but this page is not a job. '
        'editorial_seo includes salary guides, job-description templates, career advice, SEO landing pages, articles, news and informational pages even when they contain responsibilities, requirements, qualifications, salary or role keywords. documentation includes technical docs, manuals, API references, tutorials and product documentation. directory_job_board means generic listings/search/aggregation pages. '
        'Do NOT treat the phrase "job description", a role-shaped article title, responsibilities, requirements or qualifications as proof of a vacancy. Concrete apply/hiring evidence, JobPosting data, an ATS/job-item URL, or corroborated employer vacancy context is much stronger. '
        'Also assess whether the page is genuinely relevant to the candidate profile and classify the working arrangement from the page evidence. Do not interpret remote access/remote systems as a remote job. '
        'Return JSON only with keys: purpose, confidence (0-100), actionable (boolean), profile_relevant (boolean), relevance_confidence (0-100), reason, lead_actionable (boolean), lead_reason, fit_score (0-100), fit_confidence (0-100), fit_reason, recommendation (Apply Now/Review/Information Only/Reject/Unknown), remote_status (fully_remote/remote/hybrid/onsite/unknown), remote_label, remote_confidence (0-100), remote_reason, company_country, role_title, company_name, highlight. role_title should be the concise actual role name only when this page/comment clearly represents one role; otherwise leave it blank. company_name should be the actual hiring organization when it is explicit in the page/comment; never use the hosting community/job board as the employer. For job_opportunity or contract_project, company_country should be the explicit job/work-location country when the page gives one; for company_hiring_signal or company_outreach_target, use the employer/company country. Do not confuse a hosting site, navigation/footer office list, or candidate operating location with the job/employer location. Treat explicit ONSITE/on-site or hybrid wording plus office cities as non-remote unless the listing separately offers remote work. '
        'For job_opportunity or contract_project, highlight must be a concise technical summary grounded in the fetched page. Prefer about 25-40 words and never exceed 50 words; focus on concrete role technologies, subsystems, responsibilities and work area, without generic candidate-fit commentary. Do not write generic recommendation prose such as highly relevant, actionable, strong match, clear opportunity, or aligns with the candidate. '
        'Only set actionable=true for job_opportunity or contract_project. Only set lead_actionable=true for company_hiring_signal or company_outreach_target when contacting the organization itself would make practical sense now. For editorial/documentation pages, topical relevance alone is NOT enough for a lead.\n\n'
        'CURRENT ADMISSION POLICY:\n'+selectivity_instruction('opportunities')+' '+selectivity_instruction('hidden_leads')+'\n\n'
        'CANDIDATE/CAMPAIGN SCOPE:\n'+json.dumps(_local_profile_scope(campaign,grounded),ensure_ascii=False)+'\n\n'
        'DETERMINISTIC SIGNALS:\n'+json.dumps({'role_gate':role_gate,'structural_actionability':structural},ensure_ascii=False)+'\n\n'
        f'TITLE: {title}\nCOMPANY: {company}\nURL: {url}\n\nFETCHED PAGE TEXT:\n{str(page_text or "")[:18000]}'
    )
    raw=generate_with_route(route,prompt,stage='first_filter',timeout=90,subject={'type':'task','id':'local-page-purpose','label':f'Local page gate: {company or title}'})
    row=_model_json_object(raw)
    purpose=str(row.get('purpose') or 'other').strip().lower()
    if purpose not in _LOCAL_PAGE_PURPOSES: purpose='other'
    def pct(key,default=0):
        try: return max(0,min(100,int(row.get(key) if row.get(key) is not None else default)))
        except Exception: return max(0,min(100,int(default or 0)))
    def truthy(value):
        if isinstance(value,bool): return value
        if isinstance(value,(int,float)): return bool(value)
        return str(value or '').strip().lower() in {'1','true','yes','y'}
    remote=str(row.get('remote_status') or 'unknown').strip().lower()
    if remote not in _LOCAL_REMOTE_STATES: remote='unknown'
    default_label={'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}[remote]
    review={
        'purpose':purpose,'confidence':pct('confidence'),'actionable':truthy(row.get('actionable')),
        'profile_relevant':truthy(row.get('profile_relevant')),'relevance_confidence':pct('relevance_confidence',row.get('confidence') or 0),
        'reason':str(row.get('reason') or '')[:1600],'lead_actionable':truthy(row.get('lead_actionable')),'lead_reason':str(row.get('lead_reason') or '')[:1600],
        'fit_score':pct('fit_score',45),'fit_confidence':pct('fit_confidence',row.get('confidence') or 0),'fit_reason':str(row.get('fit_reason') or '')[:1600],
        'recommendation':str(row.get('recommendation') or 'Unknown')[:80],
        'remote_status':remote,'remote_label':' '.join(str(row.get('remote_label') or default_label).split())[:40] or default_label,
        'remote_confidence':pct('remote_confidence'),'remote_reason':str(row.get('remote_reason') or '')[:1200],
        'company_country':_company_country_value(row.get('company_country')),
        'role_title':' '.join(str(row.get('role_title') or '').split())[:600],
        'company_name':' '.join(str(row.get('company_name') or '').split())[:220],
        'highlight':str(row.get('highlight') or '')[:600],'structural_actionability':structural,
        'source':'Local Ollama pre-persistence review','model':str(route.get('model') or '')[:200],
    }
    return review


def _local_corroborate_candidate(source, title, company, target_url):
    """Use the same local search provider for a second, exact-role corroboration pass.

    This is intentionally used only for ambiguous Local AI candidates. It never invokes
    Cloud Web and does not change Cloud Discovery behavior.
    """
    title=' '.join(str(title or '').split()).strip(); company=' '.join(str(company or '').split()).strip()
    if not source or not title:
        return {'corroborated':False,'reason':'No search provider/title available for local corroboration.','evidence':[]}
    query=f'"{title[:180]}"'+(f' "{company[:120]}"' if company else '')
    rows,err=search_source(source,query,limit=4,usage_category='search_corroboration')
    if err:
        return {'corroborated':False,'reason':'Corroboration search failed: '+str(err)[:300],'evidence':[]}
    original=canonical(target_url)
    evidence=[]
    nt=_norm(title)
    original_domain=registrable_domain(target_url)
    for hit in rows or []:
        url=unwrap_search_result_url(str(hit.get('url') or ''))
        if not url.startswith(('http://','https://')) or canonical(url)==original:
            continue
        ht=' '.join(str(hit.get('title') or '').split()).strip(); hs=' '.join(str(hit.get('snippet') or '').split()).strip()
        sim=SequenceMatcher(None,nt,_norm(ht)).ratio() if ht else 0
        parts=urllib.parse.urlsplit(url); host=(parts.hostname or '').lower(); path=(parts.path or '').lower()
        concrete=any(host==h or host.endswith('.'+h) for h in _LOCAL_ATS_HOSTS) or any(bit in path for bit in _LOCAL_JOB_PATHS)
        same_company=bool(original_domain and registrable_domain(url)==original_domain) or (company and company.casefold() in (ht+' '+hs).casefold())
        if concrete and sim>=0.55 and same_company:
            evidence.append({'url':url[:1000],'title':ht[:300],'title_similarity':round(sim,3)})
    if evidence:
        return {'corroborated':True,'reason':'Exact-role corroboration found a separate employer/ATS job-item result.','evidence':evidence[:3]}
    return {'corroborated':False,'reason':'No separate employer/ATS item corroborated this ambiguous page.','evidence':[]}


def _search_provider_error_limit():
    """Consecutive provider failures tolerated before rotating to another source/run."""
    try:
        return max(1,min(8,int(os.environ.get('SCOUTBOX_SEARCH_PROVIDER_MAX_CONSECUTIVE_ERRORS','2') or 2)))
    except Exception:
        return 2


def _search_source_with_liveness(provider, query, limit, progress_callback, progress_value, message, should_stop=None, market=None, query_language='English'):
    """Keep CampaignRun heartbeat alive while a provider request/retry is blocking.

    Progress percentage is intentionally unchanged; repeated callbacks mean "worker is
    alive", not "progress advanced". This prevents active provider waits/retries from
    being mistaken for a stalled campaign by Dashboard and the stall watchdog.
    """
    # Split before publishing progress so Dashboard never shows a synthetic query with
    # multiple site: scopes while the adapter is actually dispatching one site at a time.
    try:
        from .query_normalizer import split_multi_site_search_queries
        dispatched_queries=split_multi_site_search_queries(query)
    except Exception:
        dispatched_queries=[str(query or '').strip()]
    if len(dispatched_queries)>1:
        combined=[]; errors=[]; seen_urls=set()
        for dispatched_query in dispatched_queries:
            _check_stop(should_stop)
            dispatched_message=f'Searching {provider.name}: {dispatched_query}'
            rows,err=_search_source_with_liveness(
                provider,dispatched_query,limit,progress_callback,progress_value,
                dispatched_message,should_stop,market=market,query_language=query_language,
            )
            if err:
                errors.append(err)
                continue
            for item in rows:
                key=str(item.get('url') or item.get('link') or '').strip().lower()
                if key and key in seen_urls:
                    continue
                if key:
                    seen_urls.add(key)
                combined.append(item)
                if len(combined)>=limit:
                    break
            if len(combined)>=limit:
                break
        if combined:
            return combined[:limit],''
        return [],'; '.join(dict.fromkeys(errors)) if errors else ''

    stop_event=threading.Event()
    def heartbeat():
        # This thread exists only to prove worker liveness while a provider adapter is
        # blocked. Do not query stop state here: a transient/thread-local DB error used
        # to kill the heartbeat silently and made active searches look stalled. The main
        # worker thread still checks stop state before and after provider calls.
        close_old_connections()
        try:
            while not stop_event.wait(8):
                try:
                    _progress(progress_callback,progress_value,message)
                finally:
                    close_old_connections()
        finally:
            close_old_connections()
    thread=None
    if progress_callback:
        thread=threading.Thread(target=heartbeat,name='scoutbox-search-heartbeat',daemon=True)
        thread.start()
    try:
        return search_source(provider,query,limit=limit,market=market,query_language=query_language)
    finally:
        stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=0.2)
        _progress(progress_callback,progress_value,message)


def _signal_query_anchor(campaign, search_profile=None, rotation_offset=0):
    """Return one compact role/specialty anchor for bounded supplemental signal search."""
    candidates=[]
    for raw in (getattr(campaign,'role_families',''), getattr(campaign,'technologies','')):
        candidates.extend(' '.join(x.split()) for x in re.split(r'[,;|\n]+',str(raw or '')) if 3 <= len(' '.join(x.split())) <= 80)
    for row in (search_profile or {}).get('skills',[]) or []:
        term=str(row.get('term') if isinstance(row,dict) else row or '').strip()
        if 3 <= len(term) <= 70:
            candidates.append(term)
    out=[]; seen=set()
    for value in candidates:
        key=value.casefold()
        if key in seen: continue
        seen.add(key); out.append(value)
    if not out:
        return 'technical specialist'
    return out[int(rotation_offset or 0) % len(out)]


def _searchapi_signal_records(campaign, cfg, search_profile, markets, *, test=False, progress_callback=None, should_stop=None, rotation_offset=0, include_news=True, forum_only=False):
    """Run bounded, market-localized SearchAPI discussion/news signal discovery.

    Forums and News are deliberately *supplemental_only*: they never enter the ordinary
    provider competition. Their output is passed through ScoutBox's normal profile/local-AI
    gates and normally becomes a Hidden Lead unless a fetched forum page is a concrete job.
    """
    market=next((m for m in (markets or []) if getattr(m,'code','')!='worldwide'),None)
    if market is None:
        return [],[],{'executed':False,'reason':'No explicit non-Worldwide Discovery Market was available.','requests':0,'raw_results':0}
    anchor=_signal_query_anchor(campaign,search_profile,rotation_offset=rotation_offset)
    specs=[('SearchAPI · Google Forums',f'{anchor} hiring',8 if test else 14,'forum')]
    if include_news and not forum_only:
        specs.append(('SearchAPI · Google News',f'{anchor} hiring expansion',6 if test else 10,'news'))
        # Google Local is disabled by default. When explicitly enabled it is an employer-
        # discovery lane only: rows carry signal_only and must earn a Hidden Lead through
        # ScoutBox's existing company/hiring verification gates.
        specs.append(('SearchAPI · Google Local',f'{anchor} companies',5 if test else 8,'local'))
    records=[]; errors=[]; requests_count=0; by_engine={}
    for idx,(name,query,limit,kind) in enumerate(specs,1):
        _check_stop(should_stop)
        source=SearchSource.objects.filter(name=name,enabled=True).first()
        if source is None:
            by_engine[name]={'enabled':False,'requests':0,'raw_results':0}
            continue
        if not provider_is_usable(source):
            by_engine[name]={'enabled':True,'configured':False,'requests':0,'raw_results':0}
            continue
        if provider_budget_remaining(source)<=0:
            by_engine[name]={'enabled':True,'configured':True,'budget_exhausted':True,'requests':0,'raw_results':0}
            continue
        progress=40+idx
        _progress(progress_callback,progress,f'Checking {name} hiring signals')
        rows,err=_search_source_with_liveness(source,query,limit,progress_callback,progress,f'Searching {name}: {query}',should_stop,market=market)
        requests_count+=1
        if err:
            errors.append(f'{name}: {err}')
            by_engine[name]={'enabled':True,'configured':True,'requests':1,'raw_results':0,'error':err[:300]}
            continue
        meta=market_search_meta(market)
        accepted_rows=[]
        if kind=='local':
            # A Google Local business listing proves that an employer exists, not that it
            # is hiring. Resolve a bounded number of those businesses through localized
            # SearchAPI Google Web and only promote a company into the signal lane when a
            # careers/jobs/hiring page is independently discoverable. Google Local is off
            # by default, so this extra verification work is explicitly opt-in.
            web_source=SearchSource.objects.filter(name='SearchAPI · Google Web',enabled=True).first()
            for local_row in list(rows or [])[:3]:
                if web_source is None or not provider_is_usable(web_source) or provider_budget_remaining(web_source)<=0:
                    break
                business_url=str(local_row.get('url') or '').strip()
                try: host=(urllib.parse.urlparse(business_url).hostname or '').lower().removeprefix('www.')
                except Exception: host=''
                company=' '.join(str(local_row.get('title') or '').split()).strip()[:220]
                if not host:
                    continue
                verify_query=f'site:{host} (careers OR jobs OR hiring) "{anchor}"'
                verify_rows,verify_err=_search_source_with_liveness(
                    web_source,verify_query,5,progress_callback,progress,
                    f'Verifying {company or host} hiring pages',should_stop,market=market,
                )
                requests_count+=1
                if verify_err:
                    errors.append(f'SearchAPI · Google Web employer verification: {verify_err}')
                    continue
                for verified in verify_rows or []:
                    evidence=' '.join(str(verified.get(k) or '') for k in ('title','url','snippet')).casefold()
                    if not re.search(r'\b(careers?|jobs?|vacanc(?:y|ies)|hiring|join[ -]?us|open positions?|opportunities)\b',evidence):
                        continue
                    item=dict(verified)
                    item['company']=company
                    item['_direct_source']=False
                    item['_direct_adapter']='searchapi_google_local_verified'
                    item['_acquisition_path']='SearchAPI Google Local employer discovery → localized careers/hiring verification'
                    item['_structured_signal_evidence']=True
                    item['_community_hiring_signal']=True
                    item['_community_kind']='employer_discovery'
                    item['_signal_only']=True
                    item['_source_category_override']='employer_discovery'
                    item['_employer_discovery']=True
                    item['_employer_discovery_origin']=business_url[:1000]
                    accepted_rows.append(item)
                    break
        else:
            accepted_rows=[dict(row) for row in (rows or [])]
        for item in accepted_rows:
            item['_discovery_market']=meta.get('market','')
            item['_discovery_market_code']=meta.get('market_code','')
            item['_market_location_hint']=meta.get('market','')
            item['_supplemental_signal_source']=kind
            records.append({'result':item,'source':source,'query':query})
        by_engine[name]={'enabled':True,'configured':True,'requests':1,'raw_results':len(rows or []),'accepted_signals':len(accepted_rows),'market':meta.get('market','')}
    return records,errors,{
        'executed':bool(requests_count),'requests':requests_count,'raw_results':len(records),
        'market':getattr(market,'name',''),'market_code':getattr(market,'code',''),
        'engines':by_engine,
    }

def _capture_campaign_lead(campaign, source, target_url, page_title, page_text, result, collector=None, http_status=None, check_error='', *, local_review=None, require_local_review=False, grounded=None):
    """Keep useful company pages rejected by the role gate as campaign Hidden Leads.

    This is intentionally conservative: only company-site pages with campaign/profile
    term evidence are retained, and documentation/platform hosts stay excluded.
    """
    if not campaign or not target_url or is_general_market_host(target_url) or is_documentation_like(target_url,page_title,page_text):
        return None,False
    # A global/Hidden-Leads blacklist entry applies to the registrable domain and all
    # of its subdomains (amazon.com therefore blocks aws.amazon.com as a lead).
    if is_blacklisted_url(target_url, scope='hidden_leads'):
        return None,False
    lead_level=selectivity_current('hidden_leads')
    lead_rules=lead_policy(lead_level)
    matched=[str(x).strip() for x in (result.get('_matched_profile_terms') or []) if str(x).strip()]
    campaign_terms=[]
    for raw in (campaign.role_families,campaign.technologies,campaign.extra_text):
        campaign_terms.extend(x.strip() for x in re.split(r'[,;\n|]+',str(raw or '')) if len(x.strip())>=3)
    blob=(' '+str(page_title or '')+' '+str(page_text or '')[:18000]).lower()
    hits=[]
    for term in matched+campaign_terms:
        if term and term.lower() in blob and term.lower() not in {x.lower() for x in hits}:
            hits.append(term)
        if len(hits)>=8: break
    if not hits:
        return None,False
    company=display_company_name(company_from_page(target_url,page_title,page_text),target_url)
    if not company or is_general_market_company(company):
        return None,False
    if active_opportunity_for_company(company,target_url):
        return None,False
    if require_local_review or local_review is not None:
        try:
            review=local_review or _local_page_review(
                campaign,page_title or company,company,target_url,page_text,
                {'accepted':False,'reason':'Candidate was rejected by deterministic role-page gate.'},grounded or {},
                has_jobposting_schema=False,
            )
        except LocalAILaneBusy:
            raise
        except Exception as exc:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_lead_semantic_gate',requests=1,pages=1,errors=1,metadata={'url':target_url,'reason':'local_lead_review_failed','error':str(exc)[:500]})
            return None,False
        confidence=int(review.get('confidence') or 0)
        direct_source=bool(result.get('_direct_source'))
        # Direct job-source items are primarily evidence of recruiting, not evidence that
        # the employer wants unsolicited contract/outsource approaches. Keep that Hidden
        # Lead bar deliberately higher, while allowing unusually niche profile-specific
        # evidence (multiple concrete specialist terms) through at a still-strong level.
        niche_direct=direct_source and len(hits)>=2 and int(review.get('relevance_confidence') or 0)>=75
        lead_threshold=(68 if niche_direct else (78 if direct_source else 60))+int(lead_rules.get('semantic_delta') or 0)
        lead_threshold=max(50,min(95,lead_threshold))
        lead_campaign_ok,lead_campaign_hits=(True,[])
        if lead_rules.get('requires_campaign_anchor'):
            lead_campaign_ok,lead_campaign_hits=campaign_alignment(campaign,company,page_title+' '+page_text,level=lead_level,kind='hidden_lead')
        qualifies=bool(review.get('lead_actionable')) and str(review.get('purpose') or '') in {'company_hiring_signal','company_outreach_target'} and confidence>=lead_threshold and lead_campaign_ok
        result['_lead_selectivity']={'level':lead_level,'semantic_threshold':lead_threshold,'campaign_hits':lead_campaign_hits}
        if not qualifies:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_lead_semantic_gate',requests=1,pages=1,metadata={'url':target_url,'reason':review.get('lead_reason') or review.get('reason') or 'Company page is not an actionable direct-outreach target.','purpose':review.get('purpose'),'confidence':review.get('confidence')})
            return None,False
        result['_local_page_review']=review
    domain=registrable_domain(target_url)
    # 0.11.8: Hidden Lead admission uses a bounded minibrowser plus LLM cutoff before
    # persistence. This gate is Hidden-Leads only; opportunity and Address Book flows
    # are deliberately untouched.
    try:
        lead_gate=hidden_lead_minibrowser_admission(
            campaign,target_url,company,inspected=result.get('_inspected'),initial_title=page_title,
            initial_text=page_text,evidence=result.get('snippet') or '',hits=hits,max_pages=6,cutoff=int(lead_rules.get('minibrowser_cutoff') or 75),
        )
    except Exception as exc:
        lead_gate={'admit':False,'decision':'reject','lead_score':0,'reason':'hidden_lead_minibrowser_error','model_error':str(exc)[:500]}
    if lead_rules.get('requires_campaign_anchor') and lead_gate.get('admit'):
        strict_ok,strict_hits=campaign_alignment(campaign,lead_gate.get('company_name') or company,' '.join(str(lead_gate.get(k) or '') for k in ('summary','why_relevant','reason_to_contact'))+' '+page_text,level=lead_level,kind='hidden_lead')
        result.setdefault('_lead_selectivity',{}).update({'campaign_hits':strict_hits})
        if not strict_ok:
            lead_gate=dict(lead_gate); lead_gate['admit']=False; lead_gate['decision']='reject'; lead_gate['reason']='selectivity_missing_campaign_anchor'
    if not lead_gate.get('admit'):
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='hidden_lead_minibrowser_admission',requests=1,pages=len(lead_gate.get('pages') or []),metadata={'url':target_url,'company':company,'decision':lead_gate.get('decision'),'lead_score':lead_gate.get('lead_score'),'cutoff':lead_gate.get('cutoff'),'selectivity':lead_level,'reason':lead_gate.get('reason_to_contact') or lead_gate.get('why_relevant') or lead_gate.get('reason') or 'Hidden Lead admission score below cutoff.','rejection_risks':lead_gate.get('rejection_risks')})
        return None,False
    result['_hidden_lead_minibrowser_admission']=lead_gate
    if lead_gate.get('company_name') and is_plausible_company_name(lead_gate.get('company_name')):
        company=display_company_name(lead_gate.get('company_name'),target_url) or company
    if lead_gate.get('contact_path') and str(lead_gate.get('contact_path')).startswith(('http://','https://')):
        result['_lead_contact_url']=lead_gate.get('contact_path')
    if adult_content_reason(page_title,page_text,target_url):
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='adult_content_gate',requests=1,pages=1,metadata={'url':target_url,'reason':'adult_content'})
        return None,False
    if recycled_lead_match(company,target_url):
        return None,False
    existing=CompanyLead.objects.filter(user_deleted=False,company__iexact=company).first()
    if not existing and domain:
        existing=CompanyLead.objects.filter(user_deleted=False).filter(Q(target_url__icontains=domain)|Q(source_url__icontains=domain)).first()
    created=False
    if existing:
        lead=existing
        changed=[]
        if not lead.source_id and source:
            lead.source=source; changed.append('source')
        if not lead.country:
            country=_company_country_value((local_review or {}).get('company_country')) or infer_country(target_url,page_title+' '+page_text)
            if country: lead.country=country; changed.append('country')
        if hasattr(lead,'locations'):
            lead_locations=normalize_location_items(getattr(lead,'locations',None) or lead.country, source='lead_country', evidence=lead.country)
            if lead_locations and lead_locations != normalize_location_items(getattr(lead,'locations',None)):
                lead.locations=lead_locations; changed.append('locations')
        if not lead.target_url:
            lead.target_url=target_url; changed.append('target_url')
        if not lead.source_url:
            lead.source_url=target_url; changed.append('source_url')
        if http_status is not None:
            try: lead.target_http_status=int(http_status)
            except Exception: lead.target_http_status=None
            lead.target_checked_at=timezone.now(); lead.target_check_error=str(check_error or '')[:500]
            changed.extend(['target_http_status','target_checked_at','target_check_error'])
        if changed:
            changed=list(dict.fromkeys(changed)); changed.append('updated_at'); lead.save(update_fields=changed)
    else:
        admission=result.get('_hidden_lead_minibrowser_admission') if isinstance(result.get('_hidden_lead_minibrowser_admission'),dict) else {}
        evidence=re.sub(r'\s+',' ',str(admission.get('text') or page_text or '')).strip()[:12000]
        summary=(strip_hidden_lead_evidence_markers(admission.get('summary')) or preliminary_company_summary(company,page_title,evidence,hits))
        lead_country=(_company_country_value((local_review or {}).get('company_country')) or infer_country(target_url,page_title+' '+page_text))
        lead_locations=normalize_location_items(lead_country, source='lead_country', evidence=lead_country)
        lead=CompanyLead.objects.create(
            company=company, source=source, country=lead_country, locations=lead_locations,
            match_summary=', '.join(hits[:8]), summary=summary, evidence=evidence,
            search_url=str((result.get('_provenance') or [{}])[0].get('url') or target_url)[:1000],
            target_url=target_url[:1000], source_url=target_url[:1000], score=max(35,min(95,int((admission.get('lead_score') if admission else None) or result.get('_pre_score',45) or 45))),
            target_http_status=(int(http_status) if http_status is not None else None),
            target_checked_at=(timezone.now() if http_status is not None or check_error else None),
            target_check_error=str(check_error or '')[:500],
        )
        created=True
    if isinstance(result.get('_local_page_review'),dict) or isinstance(result.get('_hidden_lead_minibrowser_admission'),dict):
        state=dict(lead.ai_state or {})
        if isinstance(result.get('_local_page_review'),dict):
            state['local_lead_qualification']=result.get('_local_page_review')
        if isinstance(result.get('_hidden_lead_minibrowser_admission'),dict):
            state['hidden_lead_minibrowser_admission']={k:v for k,v in result.get('_hidden_lead_minibrowser_admission').items() if k!='text'}
        lead.ai_state=state
        lead.save(update_fields=['ai_state','updated_at'])
    attribute_campaign(lead,campaign)
    # Seed Company Info immediately from retained page evidence. This performs no
    # network/AI calls and is safe inside Local Discovery; asynchronous Company Research
    # can enrich age/size further after the scan.
    try:
        enrich_company_intel_from_retained(lead)
    except Exception:
        pass
    try:
        promote_record_contact_to_addressbook(
            lead,source='Source-guided Hidden Lead',source_url=target_url,
            texts=(page_text,page_title),confidence=78,queue_research=False,
        )
    except Exception:
        pass
    # Celery enrichment jobs run outside the campaign worker context. Persist the
    # originating campaign/run so their token/search usage remains attributable.
    _uctx=usage_context()
    if _uctx.get('campaign_id') or _uctx.get('campaign_run_id'):
        state=dict(lead.ai_state or {})
        state['_usage']={
            'campaign_id':_uctx.get('campaign_id') or campaign.pk,
            'campaign_run_id':_uctx.get('campaign_run_id'),
        }
        lead.ai_state=state
        lead.save(update_fields=['ai_state','updated_at'])
    if collector is not None:
        ids=collector.setdefault('ids',[])
        if lead.pk not in ids: ids.append(lead.pk)
        if created: collector['new']=int(collector.get('new',0))+1
    return lead,created



def _capture_community_hiring_signal(campaign, source, target_url, page_title, page_text, result, collector=None, http_status=None, check_error='', *, local_review=None, grounded=None):
    """Persist a verified community/news hiring signal as a Hidden Lead.

    A Reddit/HN/forum/news URL is evidence, not the employer's website. The ordinary
    Hidden Lead capture path intentionally rejects such platform hosts, so community
    signals use a separate, stricter evidence path keyed by the employer identity that
    Local AI extracted from the post/article. A signal can become an Opportunity only
    when the underlying page itself is a concrete, fetchable vacancy; otherwise it stays
    a Hidden Lead and retains the discussion/news URL as provenance.
    """
    if not campaign or not target_url or not isinstance(local_review,dict):
        return None,False
    purpose=str(local_review.get('purpose') or '')
    confidence=int(local_review.get('confidence') or 0)
    relevance_confidence=int(local_review.get('relevance_confidence') or 0)
    profile_relevant=bool(local_review.get('profile_relevant'))
    actionable=bool(local_review.get('lead_actionable') or local_review.get('actionable'))
    if purpose not in {'company_hiring_signal','company_outreach_target','job_opportunity','contract_project'} or not actionable or not profile_relevant or confidence < 60 or relevance_confidence < 55:
        return None,False

    company=' '.join(str(local_review.get('company_name') or result.get('company') or '').split()).strip()[:220]
    if not is_plausible_company_name(company):
        company=_deterministic_company_from_evidence(result.get('snippet'),page_text,page_title)
    if not is_plausible_company_name(company) or is_general_market_company(company) or is_platform_company_name(company):
        return None,False
    if is_blacklisted_url(target_url, scope='hidden_leads', company=company):
        return None,False
    if adult_content_reason(page_title,page_text,target_url):
        return None,False
    # Do not let deleting one Reddit/HN lead suppress every other employer on that shared
    # platform domain. Community recycle suppression is company-specific only.
    if CompanyLead.objects.filter(user_deleted=True,company__iexact=company).exists():
        return None,False

    matched=[str(x).strip() for x in (result.get('_matched_profile_terms') or []) if str(x).strip()]
    signal_kind=str(result.get('_community_kind') or ('news_hiring_signal' if result.get('_news_signal') else 'community_hiring_signal'))[:80]
    source_label=(source.name if source else '')[:120]
    signal={
        'kind':signal_kind,
        'url':target_url[:1000],
        'source':source_label,
        'provider_source':str(result.get('_searchapi_source_name') or '')[:220],
        'provider_domain':str(result.get('_searchapi_source_domain') or '')[:220],
        'published_at':str(result.get('published_at') or '')[:120],
        'acquisition_path':str(result.get('_acquisition_path') or '')[:160],
        'qualification_lane':('cloud_web' if result.get('_cloud_community_signal') else 'local_ai'),
        'cloud_provider':str(local_review.get('cloud_provider') or '')[:120],
        'cloud_model':str(local_review.get('cloud_model') or '')[:160],
        'purpose':('company_hiring_signal' if purpose in {'job_opportunity','contract_project'} else purpose),
        'confidence':confidence,
        'relevance_confidence':relevance_confidence,
        'at':timezone.now().isoformat(),
    }
    evidence=re.sub(r'\s+',' ',str(page_text or result.get('snippet') or '')).strip()[:12000]
    lead_country=_company_country_value(local_review.get('company_country')) or infer_country('',str(local_review.get('company_country') or ''),strict=True)
    if not lead_country:
        lead_country=infer_country(target_url,page_title+' '+page_text,strict=True)
    lead_locations=normalize_location_items(lead_country, source='community_hiring_signal', evidence=str(local_review.get('company_country') or lead_country))
    reason=' '.join(str(local_review.get('lead_reason') or local_review.get('reason') or '').split()).strip()
    summary=(reason or preliminary_company_summary(company,page_title,evidence,matched))[:4000]
    score=max(35,min(95,max(confidence,relevance_confidence,int(local_review.get('fit_score') or 0))))

    existing=CompanyLead.objects.filter(user_deleted=False,company__iexact=company).first()
    created=False
    if existing:
        lead=existing; changed=[]
        if not lead.source_id and source:
            lead.source=source; changed.append('source')
        if not lead.country and lead_country:
            lead.country=lead_country; changed.append('country')
        if hasattr(lead,'locations') and not normalize_location_items(getattr(lead,'locations',None)) and lead_locations:
            lead.locations=lead_locations; changed.append('locations')
        if not lead.match_summary and matched:
            lead.match_summary=', '.join(matched[:8]); changed.append('match_summary')
        if not lead.summary and summary:
            lead.summary=summary; changed.append('summary')
        if not lead.evidence and evidence:
            lead.evidence=evidence; changed.append('evidence')
        if not lead.source_url:
            lead.source_url=target_url[:1000]; changed.append('source_url')
        if not lead.target_url:
            lead.target_url=target_url[:1000]; changed.append('target_url')
        if score > int(lead.score or 0):
            lead.score=score; changed.append('score')
        if http_status is not None:
            try: lead.target_http_status=int(http_status)
            except Exception: lead.target_http_status=None
            lead.target_checked_at=timezone.now(); lead.target_check_error=str(check_error or '')[:500]
            changed.extend(['target_http_status','target_checked_at','target_check_error'])
        if changed:
            lead.save(update_fields=list(dict.fromkeys(changed+['updated_at'])))
    else:
        lead=CompanyLead.objects.create(
            company=company, source=source, country=lead_country, locations=lead_locations,
            match_summary=', '.join(matched[:8]), summary=summary, evidence=evidence,
            search_url=str((result.get('_provenance') or [{}])[0].get('url') or target_url)[:1000],
            target_url=target_url[:1000], source_url=target_url[:1000], score=score, status='review',
            target_http_status=(int(http_status) if http_status is not None else None),
            target_checked_at=(timezone.now() if http_status is not None or check_error else None),
            target_check_error=str(check_error or '')[:500],
        )
        created=True

    state=dict(lead.ai_state or {})
    signals=list(state.get('community_hiring_signals') or []) if isinstance(state.get('community_hiring_signals'),list) else []
    if not any(str(x.get('url') or '')==signal['url'] for x in signals if isinstance(x,dict)):
        signals.append(signal)
    state['community_hiring_signals']=signals[-12:]
    if result.get('_cloud_community_signal'):
        state['cloud_signal_qualification']=local_review
    else:
        state['local_lead_qualification']=local_review
    state['provenance']={'type':'community_hiring_signal','source':source_label,'at':timezone.now().isoformat()}
    lead.ai_state=state
    lead.save(update_fields=['ai_state','updated_at'])
    attribute_campaign(lead,campaign)

    try:
        email=find_automatic_contact_email((page_text,result.get('snippet','')),company=company,source_url=target_url)
        if email and assignable_contact_email(email,page_text) and not lead.contact_email:
            lead.contact_email=clean_contact_email(email); lead.save(update_fields=['contact_email','updated_at'])
    except Exception:
        pass
    if collector is not None:
        ids=collector.setdefault('ids',[])
        if lead.pk not in ids: ids.append(lead.pk)
        if created: collector['new']=int(collector.get('new') or 0)+1
    UsageMetric.objects.create(
        category='community_signal', provider=source_label, stage='retained_hidden_lead', requests=1, pages=1,
        metadata={'company':company,'url':target_url[:1000],'kind':signal_kind,'confidence':confidence,'relevance_confidence':relevance_confidence},
    )
    return lead,created

def infer_channel(url,title,snippet, result=None, source=None):
    if (result or {}).get('_apply_via') == 'forum' or (result or {}).get('_forum_source') or getattr(source,'source_type','') == 'forum': return 'forum'
    text=(url+' '+title+' '+snippet).lower()
    if any(x in text for x in ['greenhouse.io','lever.co','ashbyhq.com','workdayjobs','smartrecruiters','workable.com','myworkdayjobs.com']): return 'ats'
    if 'facebook.com' in text: return 'public'
    if any(x in text for x in ['reddit.com','news.ycombinator.com','github.com','gitlab.com','lobste.rs']): return 'community'
    if re.search(r'\b(email|mailto:)\b',text): return 'email'
    return 'website'



def _best_discovery_contact_email(result, page_text='', search_snippet='', company='', target_url='', *, cloud_native=False):
    texts=[page_text or '', search_snippet or '', str((result or {}).get('snippet') or '')]
    if cloud_native and (result or {}).get('_validated_emails'):
        for raw in (result.get('_validated_emails') or []):
            email=clean_contact_email(raw)
            if email and assignable_contact_email(email, ' '.join(texts)):
                return email
    # Local/fetched pages often contain a mailto: or explicit "send CV/resume to" line.
    # Use the same guarded extractor so policy/accommodation/newsletter addresses do not
    # become application contacts.
    email=find_automatic_contact_email(texts, company=company, source_url=target_url)
    if email and assignable_contact_email(email, ' '.join(texts)):
        return email
    return ''


def _norm(s): return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()


def _recycled_opportunity_match(title, company, url, page_text=''):
    """Suppress rediscovery only while a matching opportunity remains in the Recycle Bin."""
    can=canonical(url or '')
    deleted=Opportunity.objects.filter(user_deleted=True)
    if can:
        exact=deleted.filter(canonical_url=can).first()
        if exact: return exact
    nt=_norm(title); nc=_norm(company); ns=_norm(page_text)[:1200]
    if not nt: return None
    for candidate in deleted.only('id','title','company','canonical_url','description','raw_search_snippet')[:5000]:
        title_ratio=SequenceMatcher(None,nt,_norm(candidate.title)).ratio()
        if title_ratio < 0.92: continue
        old_company=_norm(candidate.company)
        if nc and old_company and SequenceMatcher(None,nc,old_company).ratio() >= 0.80:
            return candidate
        old=_norm(candidate.description or candidate.raw_search_snippet)[:1200]
        if title_ratio >= 0.975 and ns and old and SequenceMatcher(None,ns,old).ratio() >= 0.68:
            return candidate
    return None


def _applied_match(title,company,url):
    can=canonical(url)
    exact=Application.objects.select_related('opportunity').filter(deleted_at__isnull=True,opportunity__canonical_url=can).first()
    if exact: return exact
    nt=_norm(title); nc=_norm(company)
    # Do not suppress a search result solely because its title resembles a historical
    # role at some unknown company. Company-level matching is evaluated after enrichment.
    if not nt or not nc: return None
    for app in Application.objects.select_related('opportunity').filter(deleted_at__isnull=True,status__in=['applied','reply','interview','rejected','accepted','closed'])[:1000]:
        o=app.opportunity
        oc=_norm(o.company)
        company_ok=bool(oc and SequenceMatcher(None,nc,oc).ratio()>=0.82)
        title_ok=SequenceMatcher(None,nt,_norm(o.title)).ratio()>=0.86
        if company_ok and title_ok: return app
    return None


def _merge_provenance(existing, additions, limit=40):
    out=[]; seen=set()
    for item in list(existing or []) + list(additions or []):
        key=(item.get('source',''),item.get('query',''),item.get('url','')) if isinstance(item,dict) else str(item)
        if key in seen: continue
        seen.add(key); out.append(item)
        if len(out)>=limit: break
    return out





def _merge_secondary_opportunity_duplicate(dup, *, campaign, source, query, target_url, search_url, title, company, page_text, provenance, facts, result, role_location='', role_country='', lead_collector=None, reason='cross-source role-family duplicate'):
    """Fold a later-discovered representation into one primary Opportunity row."""
    now=timezone.now(); dup.last_seen=now
    existing=dict(dup.extracted_facts or {})
    existing['rediscovered_query']=query
    existing['discovery_provenance']=_merge_provenance(existing.get('discovery_provenance',[]),provenance)
    urls=list(existing.get('alternate_vacancy_urls') or [])
    for value in (dup.target_url,dup.url,target_url,search_url):
        value=str(value or '').strip()
        if value and value not in urls:
            urls.append(value[:1000])
    existing['alternate_vacancy_urls']=urls[-20:]
    merges=list(existing.get('cross_source_merges') or [])
    marker={'at':now.isoformat(),'source':str(getattr(source,'name','') or ''),'query':str(query or '')[:300],'url':str(target_url or '')[:1000],'title':str(title or '')[:300],'company':str(company or '')[:220],'reason':str(reason or '')[:300]}
    if not any(str(x.get('url') or '')==marker['url'] and str(x.get('source') or '')==marker['source'] for x in merges if isinstance(x,dict)):
        merges.append(marker)
    existing['cross_source_merges']=merges[-20:]
    dup.extracted_facts=existing
    updates=['last_seen','extracted_facts','updated_at']
    # Prefer a resolved employer URL over a job-board/search wrapper, but preserve every
    # original URL above as provenance so no source evidence is lost.
    try:
        old_target=str(dup.target_url or dup.url or '')
        if target_url and is_job_platform_host(old_target) and not is_job_platform_host(target_url):
            dup.target_url=str(target_url)[:1000]; dup.canonical_url=canonical(target_url)[:1000]
            updates.extend(['target_url','canonical_url'])
    except Exception:
        pass
    if role_country and not str(dup.country or '').strip():
        dup.country=role_country[:120]; updates.append('country')
    if role_location and not str(dup.role_location or '').strip():
        dup.role_location=role_location[:240]; updates.append('role_location')
    dup.save(update_fields=list(dict.fromkeys(updates)))
    attribute_campaign(dup,campaign)
    try:
        st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate()); st.duplicates+=1; st.save(update_fields=['duplicates'])
    except Exception:
        pass
    if lead_collector is not None:
        lead_collector['duplicates']=int(lead_collector.get('duplicates') or 0)+1
    try:
        UsageMetric.objects.create(category='discovery_filter',provider=str(getattr(source,'name','') or ''),stage='cross_source_opportunity_merge',requests=1,pages=1,metadata={'kept_opportunity_id':dup.pk,'candidate_url':str(target_url or '')[:1000],'candidate_title':str(title or '')[:300],'company':str(company or '')[:220],'reason':str(reason or '')[:300]})
    except Exception:
        pass
    return dup,False


def _store_company_concentration_overflow(anchor, *, campaign, source, query, target_url, title, company, page_text, pre_score, role_location='', role_country='', provenance=None, decision=None, lead_collector=None):
    """Retain a saturated-employer candidate as grouped provenance, not another primary row."""
    now=timezone.now(); existing=dict(anchor.extracted_facts or {})
    existing['discovery_provenance']=_merge_provenance(existing.get('discovery_provenance',[]),provenance or [])
    overflow=list(existing.get('company_concentration_overflow') or [])
    entry={
        'at':now.isoformat(),'title':str(title or '')[:300],'company':str(company or '')[:220],
        'url':str(target_url or '')[:1000],'query':str(query or '')[:300],
        'source':str(getattr(source,'name','') or ''),'fit_score':int(pre_score or 0),
        'role_location':str(role_location or '')[:240],'country':str(role_country or '')[:120],
        'reason':str((decision or {}).get('reason') or 'company concentration guard')[:500],
        'rolling_company_count':int((decision or {}).get('count') or 0),
        'materially_distinct':bool((decision or {}).get('materially_distinct')),
        'stronger_fit':bool((decision or {}).get('stronger_fit')),
    }
    key=(vacancy_url_key(entry['url']),_norm(entry['title']))
    kept=[]; seen=set()
    for item in overflow+[entry]:
        if not isinstance(item,dict):
            continue
        ikey=(vacancy_url_key(item.get('url')), _norm(item.get('title')))
        if ikey in seen:
            continue
        seen.add(ikey); kept.append(item)
    existing['company_concentration_overflow']=kept[-24:]
    existing['company_concentration']={
        'rolling_count':int((decision or {}).get('count') or 0),
        'last_overflow_at':now.isoformat(),
        'policy':'graded rolling employer concentration; similar/low-value excess roles are grouped instead of consuming primary rows',
    }
    anchor.extracted_facts=existing; anchor.last_seen=now
    anchor.save(update_fields=['extracted_facts','last_seen','updated_at'])
    attribute_campaign(anchor,campaign)
    try:
        st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate()); st.duplicates+=1; st.save(update_fields=['duplicates'])
    except Exception:
        pass
    if lead_collector is not None:
        lead_collector['duplicates']=int(lead_collector.get('duplicates') or 0)+1
    try:
        UsageMetric.objects.create(category='discovery_filter',provider=str(getattr(source,'name','') or ''),stage='company_concentration_overflow',requests=1,pages=1,metadata={'anchor_opportunity_id':anchor.pk,'candidate_url':entry['url'],'candidate_title':entry['title'],'company':entry['company'],'fit_score':entry['fit_score'],'rolling_company_count':entry['rolling_company_count'],'reason':entry['reason']})
    except Exception:
        pass
    return anchor,False

def consolidate_cloud_results(records):
    """Canonical URL dedupe for already-verified Cloud rows without dropping fields.

    Local AI Discovery consolidation intentionally rebuilds a small search-hit shape before
    enrichment. Cloud rows already contain the verifier's remote/current/country/fit/age
    evidence, so rebuilding them through that path loses the fields required by the hard
    remote gate.
    """
    exact={}
    for rec in records or []:
        result=dict(rec.get('result') or {})
        url=str(result.get('url') or '').strip()
        if not url.startswith(('http://','https://')):
            continue
        key=canonical(url) or url
        provenance=list(result.get('_provenance') or [])
        if not provenance:
            provenance=[{'source':getattr(rec.get('source'),'name',''),'query':rec.get('query',''),'url':url}]
        if key not in exact:
            result['_source_obj']=rec.get('source')
            result['_provenance']=provenance
            result['_raw_hits']=int(result.get('_raw_hits') or 1)
            exact[key]=result
            continue
        cur=exact[key]
        cur['_raw_hits']=int(cur.get('_raw_hits') or 1)+int(result.get('_raw_hits') or 1)
        cur['_provenance']=_merge_provenance(cur.get('_provenance') or [],provenance)
        # Prefer richer verifier values without replacing existing facts with blanks.
        for field,value in result.items():
            if field.startswith('_') or value in (None,'',[],{}):
                continue
            old=cur.get(field)
            if old in (None,'',[],{}) or (isinstance(value,str) and isinstance(old,str) and len(value)>len(old)):
                cur[field]=value
    rows=list(exact.values())
    rows.sort(key=lambda x:(-int(x.get('_pre_score') or x.get('fit_score') or 0),-int(x.get('confidence') or 0),str(x.get('title') or '').lower()))
    return rows
def consolidate_results(records, search_profile):
    """Collapse cross-provider/query hits before any page fetch or AI enrichment.

    This is the important fan-in stage: raw search hits are cheap; page fetch, age
    checks and AI are expensive.  We first canonicalize, merge snippets/provenance,
    collapse obvious cross-post duplicates, and compute a cheap Resume-fit pre-score.
    """
    exact={}
    for rec in records:
        result=rec['result']; url=(result.get('url') or '').strip()
        if not url.startswith(('http://','https://')): continue
        can=canonical(url)
        key=can or url
        prov={'source':rec['source'].name,'query':rec.get('query',''),'url':url,'facebook_mode':result.get('facebook_mode','')}
        provenance=_merge_provenance(result.get('_provenance') or [],[prov])
        if key not in exact:
            exact[key]={
                'title':clean_placeholder(result.get('title'), 'Untitled opportunity'), 'url':url, 'snippet':result.get('snippet',''),
                'company':result.get('company',''), 'remote_text':result.get('remote_text',''),
                'published_at':result.get('published_at'), 'facebook_mode':result.get('facebook_mode',''),
                'cloud_discovery':bool(result.get('cloud_discovery')), 'cloud_provider':result.get('cloud_provider',''), 'cloud_model':result.get('cloud_model',''),
                '_source_obj':rec['source'], '_provenance':provenance, '_raw_hits':1,
                '_direct_source':bool(result.get('_direct_source')), '_direct_adapter':result.get('_direct_adapter',''),
                '_direct_item_id':result.get('_direct_item_id',''), '_acquisition_path':result.get('_acquisition_path',''),
                '_publication_authoritative':bool(result.get('_publication_authoritative')),
                '_community_thread_url':result.get('_community_thread_url',''), '_community_thread_title':result.get('_community_thread_title',''),
                '_ats_board':result.get('_ats_board',''), '_reddit_subreddit':result.get('_reddit_subreddit',''), '_reddit_author':result.get('_reddit_author',''),
                '_forum_source': bool(result.get('_forum_source') or getattr(rec.get('source'), 'source_type', '') == 'forum'),
                '_forum_name': result.get('_forum_name',''), '_forum_base_url': result.get('_forum_base_url',''),
                '_forum_software': result.get('_forum_software',''), '_forum_search_path': result.get('_forum_search_path',''),
                '_forum_post_date': result.get('_forum_post_date',''), '_forum_post_id': result.get('_forum_post_id',''),
                '_forum_query': result.get('_forum_query',''), '_source_category_override': result.get('_source_category_override',''),
                '_apply_via': result.get('_apply_via',''), '_role_location_hint':result.get('_role_location_hint',''),
                '_market_location_hint':result.get('_market_location_hint',''),
                '_community_hiring_signal':bool(result.get('_community_hiring_signal')), '_community_kind':result.get('_community_kind',''),
                '_structured_signal_evidence':bool(result.get('_structured_signal_evidence')), '_news_signal':bool(result.get('_news_signal')),
                '_signal_only':bool(result.get('_signal_only')), '_searchapi_source_name':result.get('_searchapi_source_name',''),
                '_searchapi_source_domain':result.get('_searchapi_source_domain',''), '_supplemental_signal_source':result.get('_supplemental_signal_source',''),
                '_discovery_market':result.get('_discovery_market',''), '_discovery_market_code':result.get('_discovery_market_code',''),
                '_multilingual_language':result.get('_multilingual_language',''), '_multilingual_source':result.get('_multilingual_source',''),
            }
        else:
            item=exact[key]; item['_raw_hits']+=1; item['_provenance']=_merge_provenance(item['_provenance'],provenance)
            # Prefer the more informative title/snippet without concatenating search-engine boilerplate forever.
            if len(result.get('title') or '') > len(item.get('title') or ''): item['title']=result.get('title')
            sn=result.get('snippet','')
            if sn and sn not in item.get('snippet',''):
                item['snippet']=(item.get('snippet','')+' '+sn).strip()[:6000]
            if result.get('published_at') and not item.get('published_at'): item['published_at']=result.get('published_at')
            if result.get('company') and not item.get('company'): item['company']=result.get('company')
            if result.get('remote_text') and not item.get('remote_text'): item['remote_text']=result.get('remote_text')
            if result.get('cloud_discovery'):
                item['cloud_discovery']=True; item['cloud_provider']=result.get('cloud_provider',''); item['cloud_model']=result.get('cloud_model','')
            if result.get('_multilingual_language') and not item.get('_multilingual_language'):
                for field in ('_discovery_market','_discovery_market_code','_multilingual_language','_multilingual_source'):
                    if result.get(field): item[field]=result.get(field)
            else:
                for field in ('_discovery_market','_discovery_market_code'):
                    if result.get(field) and not item.get(field): item[field]=result.get(field)
            if result.get('_direct_source'):
                item['_direct_source']=True
                for field in ('_direct_adapter','_direct_item_id','_acquisition_path','_community_thread_url','_community_thread_title','_ats_board','_reddit_subreddit','_reddit_author','_forum_name','_forum_base_url','_forum_software','_forum_search_path','_forum_post_date','_forum_post_id','_forum_query','_source_category_override','_apply_via','_role_location_hint','_market_location_hint'):
                    if result.get(field) and not item.get(field): item[field]=result.get(field)
                item['_publication_authoritative']=bool(item.get('_publication_authoritative') or result.get('_publication_authoritative'))
            if result.get('_community_hiring_signal') or result.get('_structured_signal_evidence') or result.get('_news_signal'):
                item['_community_hiring_signal']=bool(item.get('_community_hiring_signal') or result.get('_community_hiring_signal'))
                item['_structured_signal_evidence']=bool(item.get('_structured_signal_evidence') or result.get('_structured_signal_evidence'))
                item['_news_signal']=bool(item.get('_news_signal') or result.get('_news_signal'))
                item['_signal_only']=bool(item.get('_signal_only') or result.get('_signal_only'))
                for field in ('_community_kind','_searchapi_source_name','_searchapi_source_domain','_supplemental_signal_source','_source_category_override','_apply_via','_market_location_hint'):
                    if result.get(field) and not item.get(field): item[field]=result.get(field)
            if result.get('_forum_source') or getattr(rec.get('source'), 'source_type', '') == 'forum':
                item['_forum_source']=True
                for field in ('_forum_name','_forum_base_url','_forum_software','_forum_search_path','_forum_post_date','_forum_post_id','_forum_query','_source_category_override','_apply_via','_role_location_hint','_market_location_hint'):
                    if result.get(field) and not item.get(field): item[field]=result.get(field)
                if result.get('_publication_authoritative'):
                    item['_publication_authoritative']=True

    # Conservative cross-URL collapse for the same indexed role through redirects/cross-posts.
    groups=[]
    for item in exact.values():
        nt=_norm(item.get('title'))
        merged=None
        for candidate in groups:
            ct=_norm(candidate.get('title'))
            title_sim=SequenceMatcher(None,nt,ct).ratio() if nt and ct else 0
            sn=_norm(item.get('snippet',''))[:1200]; cs=_norm(candidate.get('snippet',''))[:1200]
            snippet_sim=SequenceMatcher(None,sn,cs).ratio() if sn and cs else 0
            # Same generic titles at different companies must not collapse. Cross-URL grouping
            # therefore requires an almost identical title plus substantial snippet evidence.
            if title_sim>=0.985 and snippet_sim>=0.72:
                merged=candidate; break
        if not merged:
            groups.append(item); continue
        merged['_raw_hits']+=item['_raw_hits']
        merged['_provenance']=_merge_provenance(merged['_provenance'],item['_provenance'])
        if len(item.get('snippet',''))>len(merged.get('snippet','')): merged['snippet']=item['snippet']

    for item in groups:
        score,matches=pre_score_hit(item.get('title',''),item.get('snippet',''),search_profile)
        # Multiple independent providers/queries finding the same result is mild corroboration.
        independent_sources=len({p.get('source') for p in item['_provenance']})
        independent_queries=len({p.get('query') for p in item['_provenance']})
        item['_pre_score']=min(100,score+min(6,max(0,independent_sources-1)*2)+min(4,max(0,independent_queries-1)))
        item['_matched_profile_terms']=matches
    groups.sort(key=lambda x:(-x['_pre_score'],-x['_raw_hits'],x.get('title','').lower()))
    return groups


# Large multi-employer job aggregators are discovery pointers, not authoritative
# opportunity pages. Prefer direct employer/ATS results and never persist these as
# an Opportunity merely because a search engine surfaced them.
# 0.10.90: listing-platform identity is centralized. Public job boards are discovery
# pointers; direct ATS role pages remain valid exact-role destinations.
def _is_job_aggregator_url(url):
    return is_job_board_host(url)

def _is_third_party_job_url(url):
    return is_job_board_host(url)


def _record_direct_site_activity(url, purpose, *, ok=False, status=None, bytes_count=0, provider='Direct HTTP', metadata=None):
    try:
        UsageMetric.objects.create(
            category='direct_site', provider=provider, stage=str(purpose or 'direct_fetch')[:80],
            requests=1, pages=1 if ok else 0, bytes_downloaded=max(0,int(bytes_count or 0)),
            errors=0 if ok else 1,
            metadata={'url':str(url or '')[:1000],'http_status':status,**(metadata or {})},
        )
    except Exception:
        pass


def _direct_fetch(url, title='', snippet='', *, purpose='direct_fetch', timeout=18):
    fetched=fetch_target(url,title,snippet,timeout=timeout)
    _record_direct_site_activity(
        fetched.get('target_url') or url, purpose, ok=bool(fetched.get('ok')),
        status=fetched.get('http_status'), bytes_count=fetched.get('bytes') or 0,
        metadata={'title':str(fetched.get('title') or title)[:250],'error':str(fetched.get('error') or '')[:300]},
    )
    return fetched


def _searchapi_corroborate_community_signal(result, title, company, target_url, page_text):
    """Optionally corroborate a native HN/Reddit/forum signal with verified public pages.

    This is deliberately sparse: SearchAPI AI research is disabled by default, has its own
    automatic daily cap, shares the account limit, and the research router declines to run
    when a direct OpenAI/Gemini/OpenRouter credential is available. AI text alone is never
    retention evidence; at least one returned URL must be fetched and contain explicit
    hiring/careers language before its text is appended for the normal Local AI gates.
    """
    if not result.get('_community_hiring_signal') or result.get('_structured_signal_evidence'):
        return page_text
    code=str(result.get('_discovery_market_code') or '').strip().lower()
    market=MARKET_BY_CODE.get(code)
    if market is None:
        return page_text
    subject=(' at '+company) if is_plausible_company_name(company) else ''
    query=(
        f'Verify the current public hiring signal for "{title[:180]}"{subject}. '
        f'The community source {target_url[:650]} is evidence only. Find an official careers/ATS page '
        'or another current public source that independently confirms hiring, and cite the sources.'
    )[:3500]
    try:
        research=searchapi_research(query,market=market,purpose='community_signal_corroboration',automatic=True,limit=5)
    except Exception:
        return page_text
    if not research.get('ok'):
        return page_text
    verified=[]
    hiring_re=re.compile(r'(?i)\b(careers?|jobs?|vacanc(?:y|ies)|hiring|we[’\']?re hiring|join (?:our|the) team|open positions?|opportunities)\b')
    for ref in (research.get('results') or [])[:4]:
        ref_url=str(ref.get('url') or '').strip()
        if not ref_url.startswith(('http://','https://')) or canonical(ref_url)==canonical(target_url) or is_search_engine_url(ref_url):
            continue
        fetched=_direct_fetch(ref_url,str(ref.get('title') or ''),str(ref.get('snippet') or ''),purpose='community_signal_corroboration',timeout=15)
        if not fetched.get('ok') or int(fetched.get('http_status') or 0) in (404,410):
            continue
        evidence=' '.join((str(fetched.get('title') or ''),str(fetched.get('text') or '')[:12000],ref_url))
        if not hiring_re.search(evidence):
            continue
        verified.append({
            'url':str(fetched.get('target_url') or ref_url)[:1000],
            'title':str(fetched.get('title') or ref.get('title') or '')[:300],
            'text':str(fetched.get('text') or '')[:8000],
        })
        if len(verified)>=2:
            break
    if not verified:
        return page_text
    result['_searchapi_research_corroboration']=[{'url':x['url'],'title':x['title']} for x in verified]
    extra='\n\n'.join(f"Corroborating public source: {x['title']}\n{x['url']}\n{x['text']}" for x in verified)
    return (str(page_text or '')+'\n\n'+extra)[:45000]


def _direct_role_candidate(title, company, board_url, url, hit_title='', snippet='', provider='', query=''):
    if not url.startswith(('http://','https://')) or canonical(url)==canonical(board_url):
        return None
    if _is_third_party_job_url(url) or is_search_engine_url(url):
        return None
    fetched=_direct_fetch(url,hit_title,snippet,purpose='employer_role_lookup')
    if not fetched.get('ok') or int(fetched.get('http_status') or 0) in (404,410):
        return None
    final=unwrap_search_result_url(str(fetched.get('target_url') or url))
    if _is_third_party_job_url(final) or is_search_engine_url(final):
        return None
    final_title=sanitize_mixed_script_title(' '.join(str(fetched.get('title') or hit_title).split()).strip())
    content=str(fetched.get('text') or '')
    if soft_missing_reason(final_title,content):
        return None
    valid=_replacement_role_page_valid(title,company,final,fetched)
    if not valid.get('accepted'):
        return None
    return {'url':final,'fetched':fetched,'provider':provider or 'Direct HTTP','query':query,
            'title_similarity':valid.get('title_similarity',0),'validation':valid}


def _replacement_role_page_valid(title, company, url, fetched):
    """Validate an employer/ATS replacement against *its own* fetched content.

    Validation from the third-party source must never be inherited by a different URL.
    A replacement needs strong title identity, concrete vacancy/actionability structure,
    and employer corroboration before it is even eligible for semantic re-review.
    """
    fetched=fetched or {}; final_title=sanitize_mixed_script_title(' '.join(str(fetched.get('title') or '').split()).strip())
    content=str(fetched.get('text') or '')
    gate=classify_role_page(url,final_title or title,content,has_jobposting_schema=bool(fetched.get('has_jobposting_schema')),is_pdf=bool(fetched.get('is_pdf')))
    structural=_local_action_signals(url,content,has_jobposting_schema=bool(fetched.get('has_jobposting_schema')))
    nt=_norm(title); title_sim=SequenceMatcher(None,nt,_norm(final_title)).ratio() if nt and final_title else 0.0
    expected_tokens=[x for x in re.findall(r'[a-z0-9+#.]+',nt) if len(x)>=3 and x not in {'senior','lead','principal','staff','engineer','developer','specialist','remote'}]
    title_blob=_norm(final_title+' '+content[:5000])
    distinctive_matches=sum(1 for token in set(expected_tokens) if token in title_blob)
    if gate.get('hard_reject'):
        return {'accepted':False,'reason':gate.get('reason','hard reject'),'title_similarity':round(title_sim,3),'gate':gate,'structural':structural}
    if title_sim < 0.62 and (expected_tokens and distinctive_matches < min(2,len(set(expected_tokens)))):
        return {'accepted':False,'reason':'replacement role title does not strongly match the discovered vacancy','title_similarity':round(title_sim,3),'gate':gate,'structural':structural}
    if not gate.get('accepted') or not structural.get('clear'):
        return {'accepted':False,'reason':'replacement page is not a concrete actionable vacancy','title_similarity':round(title_sim,3),'gate':gate,'structural':structural}
    company_norm=_norm(company)
    if company_norm:
        recovered_company=''
        try:
            recovered_company=display_company_name(company_from_page(url,final_title,content),url)
        except Exception:
            recovered_company=''
        recovered_norm=_norm(recovered_company)
        if recovered_norm and SequenceMatcher(None,company_norm,recovered_norm).ratio() < 0.70:
            return {'accepted':False,'reason':'replacement page identifies a different employer', 'replacement_company':recovered_company[:120], 'title_similarity':round(title_sim,3),'gate':gate,'structural':structural}
        if not recovered_norm:
            # Do not let an arbitrary technology/product mention deep in the JD corroborate
            # employer identity (for example "Splunk Phantom" is not employer Phantom).
            strong_zone=_norm(final_title+' '+content[:1800]+' '+url)
            try: host_norm=_norm((urllib.parse.urlsplit(url).hostname or '').split('.')[0])
            except Exception: host_norm=''
            if company_norm not in strong_zone and (not host_norm or SequenceMatcher(None,company_norm,host_norm).ratio()<0.58):
                return {'accepted':False,'reason':'replacement page does not corroborate the employer identity','title_similarity':round(title_sim,3),'gate':gate,'structural':structural}
    return {'accepted':True,'reason':'replacement page independently verifies the same concrete vacancy','title_similarity':round(title_sim,3),'gate':gate,'structural':structural}


def _prefer_exact_employer_role(title, company, board_url):
    """Resolve third-party job-board discoveries to the employer/ATS role page.

    Search exact role/company first, then company careers queries. If only a careers page is
    found, fetch it directly and inspect its role links. Generic careers roots are discovery
    aids only and are never persisted as Opportunities.
    """
    if not _is_third_party_job_url(board_url) or not title or not company:
        return None
    providers,_meta=provider_selection_details(limit=2)
    if not providers:
        return None
    queries=[f'"{title[:180]}" "{company[:120]}"',
             f'"{company[:120]}" careers "{title[:180]}"',
             f'"{company[:120]}" jobs "{title[:180]}"',
             f'"{company[:120]}" careers']
    error_limit=_search_provider_error_limit()
    for provider in providers[:2]:
        consecutive_errors=0
        for query in queries:
            rows,err=search_source(provider,query,limit=8,usage_category='employer_role_lookup')
            if err:
                consecutive_errors+=1
                if consecutive_errors>=error_limit: break
                continue
            consecutive_errors=0
            for hit in rows or []:
                url=unwrap_search_result_url(str(hit.get('url') or '').strip())
                hit_title=sanitize_mixed_script_title(' '.join(str(hit.get('title') or '').split()).strip())
                direct=_direct_role_candidate(title,company,board_url,url,hit_title,str(hit.get('snippet') or ''),provider.name,query)
                if direct:
                    return direct
                # Career root/search page fallback: direct-fetch and inspect employer/ATS links.
                if not url.startswith(('http://','https://')) or _is_third_party_job_url(url) or is_search_engine_url(url):
                    continue
                if not re.search(r'(?i)(careers?|jobs?|join[-_/ ]?us|vacanc)',url+' '+hit_title):
                    continue
                root=_direct_fetch(url,hit_title,str(hit.get('snippet') or ''),purpose='employer_career_page')
                if not root.get('ok') or not root.get('html'):
                    continue
                try:
                    soup=BeautifulSoup(root.get('html') or '','html.parser')
                    links=[]
                    for a in soup.find_all('a',href=True):
                        text=' '.join(a.get_text(' ',strip=True).split())
                        href=urllib.parse.urljoin(root.get('target_url') or url,a.get('href'))
                        sim=SequenceMatcher(None,_norm(title),_norm(text)).ratio() if text else 0
                        if sim>=0.42 or (_norm(title) and _norm(title) in _norm(text)):
                            links.append((sim,href,text))
                    for _sim,href,text in sorted(links,reverse=True)[:12]:
                        direct=_direct_role_candidate(title,company,board_url,href,text,'',provider.name,query+' [career-page link]')
                        if direct:
                            return direct
                except Exception:
                    continue
    return None

def _limit_job_board_candidates(rows, per_board=12):
    """Keep a noisy job board from monopolizing one Local AI Discovery run.

    Rows are already sorted by cheap Resume-fit score. Direct employer/ATS domains are
    untouched; only known multi-employer boards are capped before expensive page fetches.
    """
    out=[]; counts={}; dropped=0
    for item in rows or []:
        url=str(item.get('url') or '')
        if not _is_job_aggregator_url(url):
            out.append(item); continue
        try:
            host=(urllib.parse.urlsplit(url).netloc or '').lower().removeprefix('www.')
        except Exception:
            host=''
        labels=set(host.split('.'))
        brand=registrable_domain(host) or host or 'job-board'
        count=counts.get(brand,0)
        if count>=max(1,int(per_board or 12)):
            dropped+=1; continue
        counts[brand]=count+1; out.append(item)
    return out,dropped


def _is_job_aggregator_collection_url(url):
    """Recognize search/list URLs on large job boards even when one job is selected."""
    try:
        parts=urllib.parse.urlsplit(url or ''); host=(parts.netloc or '').lower().removeprefix('www.'); path=(parts.path or '').lower(); qs=urllib.parse.parse_qs(parts.query)
    except Exception:
        return False
    if not _is_job_aggregator_url(url): return False
    if host.endswith('indeed.com') or host.startswith('indeed.') or '.indeed.' in host:
        # Indeed list pages may carry ?vjk=<job> to select a side-panel job. The page
        # is still a multi-role search result and must never become one Opportunity.
        if re.match(r'^/q-.+-jobs\.html/?$',path): return True
        if path.rstrip('/') in ('/jobs','/jobs/search','/jobs/browse'): return True
    if host.endswith('linkedin.com') and any(path.startswith(x) for x in ('/jobs/search','/jobs/collections','/jobs/search-results')): return True
    if (host.endswith('glassdoor.com') or host.startswith('glassdoor.') or '.glassdoor.' in host) and any(x in path for x in ('/job/jobs.htm','/job/index.htm','/job/search')): return True
    if any(x in path for x in ('/jobs/search','/search/jobs','/job-search','/jobs/browse','/jobs/category','/jobs/location')): return True
    query_keys={str(k).lower() for k in qs}
    if query_keys.intersection({'q','query','keyword','keywords','location','where','search'}) and any(x in path for x in ('/job','/jobs','/search')):
        return True
    return False


def _aggregate_collection_fetch_url(url):
    """Remove UI-only selected-job parameters before expanding an aggregate list page."""
    if not _is_job_aggregator_collection_url(url): return url
    try:
        parts=urllib.parse.urlsplit(url); pairs=urllib.parse.parse_qsl(parts.query,keep_blank_values=True)
        pairs=[(k,v) for k,v in pairs if k.lower() not in {'vjk','selectedjob','currentjob','jobkey'}]
        return urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,urllib.parse.urlencode(pairs),'')).rstrip('?')
    except Exception:
        return url


def _looks_like_job_detail_url(url):
    """Recognize a single-role URL on a job board without trusting board landing pages."""
    try:
        parts=urllib.parse.urlsplit(url or ''); path=(parts.path or '').lower(); qs=urllib.parse.parse_qs(parts.query)
    except Exception:
        return False
    if _is_job_aggregator_collection_url(url): return False
    if any(k in qs for k in ('jk','jobid','job_id','jobkey','jobkeyid')): return True
    if any(x in path for x in ('/viewjob','/jobs/view/','/job/view/','/job-listing/','/position/','/positions/')): return True
    if '/job/' in path and path.rstrip('/') not in ('/job','/jobs'): return True
    # Some boards use /jobs/<slug-or-id> for detail pages. Keep obvious list/search paths out.
    if '/jobs/' in path:
        tail=path.split('/jobs/',1)[1].strip('/')
        if tail and not any(tail.startswith(x) for x in ('search','browse','category','remote','location')): return True
    return False


_JOB_COUNT_PATTERN=r'(?:\d{1,3}(?:[,.]\d{3})+|\d+)\+?'
_AGGREGATE_TEXT_PATTERNS=(
    re.compile(rf'(?i)\bsearch\s+{_JOB_COUNT_PATTERN}\s+.+?jobs?\b'),
    re.compile(rf'(?i)\b{_JOB_COUNT_PATTERN}\s+.+?jobs?\b(?:\s+in\b|.*\b(?:added|hiring|openings?|positions?)\b)'),
    re.compile(r'(?i)\bapply to (?:flexible|remote|\d[\d,.]*\+?) positions?\b'),
    re.compile(r'(?i)\bwork anywhere\b.*\b(?:jobs?|positions?)\b'),
    re.compile(r'(?i)\bflexible\s+(?:remote\s+)?[^\n]{0,100}jobs?\b'),
    re.compile(r'(?is)\bview all\s+.{0,180}\s+jobs\s+in\b.{0,500}\bsalary search:\b.{0,500}\bsee popular questions\s*&\s*answers about\b'),
    re.compile(r'(?i)\bemployers register for free\b.*\bpost a job\b.*\bcustomer service\b'),
)
_JOB_COLLECTION_TITLE_RE=re.compile(rf'(?i)^\s*{_JOB_COUNT_PATTERN}\s+.+?\bjobs?\b(?:\s+in\b.*)?\s*$')

def _looks_like_job_collection_title(title=''):
    label=re.sub(r'\s+',' ',str(title or '')).strip()
    return bool(
        _JOB_COLLECTION_TITLE_RE.search(label)
        or re.search(r'(?i)^\s*flexible\s+(?:remote\s+)?[^\n]{0,120}jobs?\b',label)
        or re.search(r'(?i)\bjobs\s*(?:,\s*employment)?(?:\s+in\s+[^|]{2,120})?(?:\s*[|–—-]\s*(?:indeed|glassdoor|linkedin|ziprecruiter))?\s*$',label)
        or re.search(r'(?i)^\s*.+?\s+jobs?\s+in\s+[^|–—]{2,120}(?:\s*[|–—-]\s*(?:indeed|jobstreet|jobsdb|seek|glassdoor|linkedin))?\s*$',label)
        or re.search(r'(?i)\bjob search\b',label)
    )

def _search_snippet_is_aggregate(title='',text=''):
    blob=re.sub(r'\s+',' ',f'{title} {text}').strip()[:6000]
    return _looks_like_job_collection_title(title) or any(p.search(blob) for p in _AGGREGATE_TEXT_PATTERNS)

def _aggregate_job_page(url,title='',text=''):
    try:
        parts=urllib.parse.urlsplit(url or ''); path=parts.path.lower(); qs=urllib.parse.parse_qs(parts.query)
    except Exception:
        return False
    if _looks_like_job_collection_title(title): return True
    if _is_job_aggregator_url(url) and not _looks_like_job_detail_url(url): return True
    label=(title or '').lower(); sample=(text or '')[:5000].lower()
    if _search_snippet_is_aggregate(label,sample): return True
    if ('page' in qs or 'sort' in qs) and any(x in path for x in ('/jobs/','/careers/','/positions/')): return True
    if any(x in label for x in (' jobs - remote','remote jobs','job search','open positions')) and sample.count('apply')>=3: return True
    # Generic list pages often expose many job-like headings/links even when the URL is opaque.
    job_mentions=len(re.findall(r'(?i)\b(?:engineer|developer|designer|manager|analyst|specialist|architect|technician)\b',sample))
    if sample.count('apply')>=5 and job_mentions>=5: return True
    return False


def _aggregate_child_snippet(anchor):
    """Keep a compact listing-card excerpt with each extracted child role."""
    node=anchor
    for _ in range(4):
        node=getattr(node,'parent',None)
        if node is None: break
        name=getattr(node,'name','')
        if name in ('article','li'):
            text=' '.join(node.stripped_strings).strip()
            if text: return text[:1200]
        attrs=getattr(node,'attrs',{}) or {}; classes=' '.join(attrs.get('class') or []).lower(); testid=str(attrs.get('data-testid') or '').lower()
        if 'job' in classes or 'job' in testid or 'result' in classes:
            text=' '.join(node.stripped_strings).strip()
            if text: return text[:1200]
    return ''


def _expand_aggregate_record(record, limit=25):
    """Turn search/list pages into individual job URLs before enrichment.

    This intentionally includes known aggregators such as Indeed. Their list page is
    never treated as one opportunity; its child role pages are fetched later through
    the normal validation/enrichment pipeline.
    """
    result=record.get('result') or {}; url=(result.get('url') or '').strip()
    if not url.startswith(('http://','https://')): return []
    # Community/news results are evidence records, not aggregator landing pages. Expanding
    # an HN/Reddit/forum page into every linked URL destroys the post-level hiring signal
    # and was one reason community sources produced almost no retained results.
    if result.get('_community_hiring_signal') or result.get('_structured_signal_evidence') or result.get('_news_signal'):
        return [record]
    is_board=_is_job_aggregator_url(url)
    original_collection=_is_job_aggregator_collection_url(url)
    if not is_board and not _aggregate_job_page(url,result.get('title',''),result.get('snippet','')): return [record]
    inspected=fetch_target(_aggregate_collection_fetch_url(url),result.get('title',''),result.get('snippet',''))
    if not inspected.get('ok'):
        UsageMetric.objects.create(category='discovery_filter',provider=getattr(record.get('source'),'name',''),stage='aggregate_fetch_failed',requests=1,pages=1,errors=1,metadata={'url':url,'error':str(inspected.get('error') or '')[:500]})
        return []
    base=inspected.get('target_url') or url
    page_title=inspected.get('title') or result.get('title',''); page_text=inspected.get('text','')
    # A direct job detail on an aggregator is valid only when the original result was
    # itself a detail URL. A collection URL with a selected-job parameter/schema is still
    # a list page and must be expanded into child role URLs instead of summarized whole.
    if _is_job_aggregator_url(base) and not original_collection and _looks_like_job_detail_url(base) and not _search_snippet_is_aggregate(page_title,page_text):
        child=dict(result); child['url']=base
        if page_title: child['title']=page_title[:300]
        return [{'result':child,'source':record.get('source'),'query':record.get('query','')}]
    if original_collection:
        # Continue into anchor expansion even if the fetched page advertises one selected
        # JobPosting schema. The URL identity is authoritative for aggregate boards.
        pass
    elif not _aggregate_job_page(base,page_title,page_text):
        return [record]
    html=inspected.get('html') or ''
    try: soup=BeautifulSoup(html,'html.parser')
    except Exception: return []
    base_host=urllib.parse.urlsplit(base).netloc.lower(); parent_can=canonical(base); out=[]; seen=set()
    for a in soup.find_all('a',href=True):
        href=urllib.parse.urljoin(base,a.get('href','')); parts=urllib.parse.urlsplit(href)
        if parts.scheme not in ('http','https'): continue
        link_host=parts.netloc.lower(); same_host=link_host==base_host
        known_ats=any(x in link_host for x in ('greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com'))
        # Company career hubs and some aggregators link directly to an external ATS.
        # Allow those child links, but not arbitrary ads/navigation off the listing page.
        if not same_host and not known_ats and not _looks_like_job_detail_url(href): continue
        can=canonical(href)
        if not can or can==parent_can or can in seen: continue
        path=parts.path.lower()
        if is_board or _is_job_aggregator_url(base):
            if not (_looks_like_job_detail_url(href) or known_ats): continue
        elif not (known_ats or _looks_like_job_detail_url(href) or any(x in path for x in ('/job/','/jobs/','/position/','/positions/','/careers/'))):
            continue
        text=' '.join(a.stripped_strings).strip()
        if len(text)<3: continue
        seen.add(can); child=dict(result); child.update({'url':href,'title':text[:300],'snippet':_aggregate_child_snippet(a)})
        provenance=list(child.get('_provenance') or [])
        provenance.append({'source':getattr(record.get('source'),'name',''),'query':record.get('query',''),'url':base,'aggregate_parent':True})
        child['_provenance']=provenance
        out.append({'result':child,'source':record.get('source'),'query':record.get('query','')})
        if len(out)>=limit: break
    UsageMetric.objects.create(category='discovery_filter',provider=getattr(record.get('source'),'name',''),stage='aggregate_expansion',requests=1,pages=1,metadata={'url':base,'children':len(out),'job_aggregator':bool(_is_job_aggregator_url(base))})
    return out

def _distinctive_cloud_note(result):
    """Keep only a small genuinely distinctive discovery signal; never force a generic note."""
    text=' '.join(str(result.get(k) or '') for k in ('fit_reason','lead_reason','snippet','evidence'))
    text=re.sub(r'\s+',' ',text).strip()
    if not text:
        return ''
    markers=('retro','legacy','niche','hard to find','hard-to-find','rare','unusual','specialist','reverse engineering','obsolete','vintage')
    low=text.casefold()
    pos=min([low.find(m) for m in markers if low.find(m)>=0] or [-1])
    if pos<0:
        return ''
    start=max(0,text.rfind('.',0,pos)+1); end=text.find('.',pos)
    if end<0 or end-start>150: end=min(len(text),start+135)
    phrase=text[start:end].strip(' -–—:;,')
    phrase=re.sub(r'(?i)^(?:this|the)\s+(?:role|opportunity|candidate|position)\s+(?:is|appears|looks|was|has)\s+', '', phrase).strip()
    if len(phrase)<8: return ''
    if len(phrase)>135:
        phrase=phrase[:135].rsplit(' ',1)[0].rstrip(' ,;:-')
    return phrase


def _cloud_company_structured(result):
    founded=''
    m=re.search(r'\b(18|19|20)\d{2}\b',str(result.get('founded_year') or ''))
    if m: founded=int(m.group(0))
    age=''
    if founded:
        years=max(0,timezone.localdate().year-founded)
        age='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
    size=''
    m=re.search(r'(?<!\d)(1[–-]10|10[–-]20|20[–-]50|50[–-]100)(?!\d)',str(result.get('company_size') or ''))
    if m: size=m.group(1).replace('-', '–')
    return {'founded_year':founded or '', 'founded_by':str(result.get('founded_by') or '')[:500], 'age_range':age, 'size_range':size, 'verified':bool(result.get('sources'))}



_FOLLOWUP_POSITIVE_RE=re.compile(r'(?i)\b(careers?|jobs?|hiring|vacanc(?:y|ies)|join(?:\s+our)?\s+team|opportunit(?:y|ies)|open\s+roles?|positions?|projects?|consult(?:ing|ancy)|collaborat(?:e|ion)|partners?|customers?|clients?|testimonials?|case\s+stud(?:y|ies)|contact|team|about|work\s+with\s+us|talent)\b')
_FOLLOWUP_NEGATIVE_RE=re.compile(r'(?i)\b(privacy|terms|cookies?|legal|login|sign\s*in|register|account|share|facebook|instagram|twitter|x\.com|linkedin|youtube|tiktok|press|news|blog|sitemap|accessibility)\b')
_FOLLOWUP_ATS_HOSTS=('greenhouse.io','lever.co','ashbyhq.com','workable.com','myworkdayjobs.com','workday.com','smartrecruiters.com','jobvite.com','bamboohr.com','icims.com','oraclecloud.com','successfactors.com')


def _followup_host(url):
    try: return urllib.parse.urlsplit(str(url or '')).netloc.lower().removeprefix('www.')
    except Exception: return ''


def _followup_allowed(parent_url, link):
    url=str((link or {}).get('url') or '').strip(); anchor=' '.join(str((link or {}).get('anchor') or '').split()); context=' '.join(str((link or {}).get('context') or '').split())
    if not url.startswith(('http://','https://')) or is_disallowed_adult_url(url): return False
    combined=(anchor+' '+context+' '+urllib.parse.urlsplit(url).path.replace('-',' ').replace('_',' '))[:1200]
    if _FOLLOWUP_NEGATIVE_RE.search(combined) and not _FOLLOWUP_POSITIVE_RE.search(combined): return False
    if not _FOLLOWUP_POSITIVE_RE.search(combined): return False
    ph=_followup_host(parent_url); ch=_followup_host(url)
    if not ch: return False
    same=bool(ph and (ch==ph or ch.endswith('.'+ph) or ph.endswith('.'+ch)))
    ats=any(ch==h or ch.endswith('.'+h) for h in _FOLLOWUP_ATS_HOSTS)
    # Arbitrary cross-domain partner/customer pages need explicit relationship context.
    cross_context=bool(re.search(r'(?i)\b(partner|customer|client|testimonial|case\s+stud|collaborat|project)\b',combined))
    return same or ats or cross_context


def _collect_followup_links(inspected, *, parent_url, source, query, depth, collector, inherited_matches=None):
    if collector is None: return
    for link in (inspected or {}).get('links') or []:
        if not _followup_allowed(parent_url,link): continue
        url=canonical(str(link.get('url') or ''))
        if not url or url in collector['seen']: continue
        collector['seen'].add(url)
        collector['queue'].append({
            'result':{
                'url':url,'title':str(link.get('anchor') or '')[:300],
                'snippet':str(link.get('context') or '')[:2000],
                '_followup_source':True,'_followup_depth':int(depth)+1,
                '_matched_profile_terms':list(inherited_matches or [])[:20],
                '_acquisition_path':'Local follow-up link',
                '_provenance':[{'source':'Local follow-up link','query':query,'url':url,'parent_url':parent_url,'depth':int(depth)+1}],
            },
            'source':source,'query':query,'depth':int(depth)+1,
        })


def ingest_result(result, source, campaign, query='', lead_collector=None, filter_collector=None, search_profile=None, followup_collector=None, followup_depth=0):
    def _reject(reason):
        if filter_collector is not None:
            filter_collector[reason]=int(filter_collector.get(reason) or 0)+1

    search_url=unwrap_search_result_url((result.get('url') or '').strip())
    if not search_url.startswith(('http://','https://')):
        _reject('invalid_url')
        return None,False
    community_signal=bool(result.get('_community_hiring_signal') or result.get('_news_signal') or result.get('_structured_signal_evidence'))
    if is_disallowed_adult_url(search_url):
        _reject('adult_content')
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='adult_content_rejected',requests=1,pages=1,metadata={'url':search_url})
        return None,False
    if _is_job_aggregator_collection_url(search_url) and not result.get('_followup_source') and not community_signal:
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='aggregate_url_rejected',requests=1,pages=1,metadata={'url':search_url,'reason':'known_job_board_collection_url'})
        _reject('job_board_collection_url')
        return None,False
    # Provider click/redirect URLs (for example Bing /ck/a or Naver /l) must be
    # allowed through the fetch step so HTTP redirects can resolve the real website.
    if is_blacklisted_url(search_url, scope='opportunities'):
        _reject('blacklisted_url')
        return None,False
    now=timezone.now(); cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    search_title=clean_placeholder(result.get('title'), 'Untitled opportunity')[:300]
    search_snippet=result.get('snippet','')
    if (_looks_like_job_collection_title(search_title) or _search_snippet_is_aggregate(search_title,search_snippet)) and not result.get('_followup_source') and not community_signal:
        # Search result collection/landing-page copy is never usable as a single role.
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='aggregate_snippet_rejected',requests=1,pages=1,metadata={'url':search_url,'title':search_title,'reason':'aggregate_search_result_copy'})
        _reject('multi_role_search_result')
        return None,False
    company=clean_placeholder(result.get('company'))[:220]
    if company and (is_general_market_company(company) or is_platform_company_name(company)):
        company=''
    direct_adapter=str(result.get('_direct_adapter') or '').strip().lower()
    direct_company_adapters={
        'greenhouse','lever','ashby','smartrecruiters','remoteok','remotive','himalayas','jobicy',
        'wwr_rss','linkedin_job_library','glassdoor_jobs','wellfound_page',
    }
    ats_url_company=company_from_ats_url(search_url)
    if direct_adapter in {'greenhouse','lever','ashby','smartrecruiters'} and ats_url_company:
        company=ats_url_company
    authoritative_direct_company=bool(
        result.get('_direct_source') and direct_adapter in direct_company_adapters and
        company and is_plausible_company_name(company)
    )
    company_identity_source=('direct_'+direct_adapter if authoritative_direct_company else '')
    company_identity_confidence=(96 if authoritative_direct_company else 0)
    company_identity_reason=('Employer identity supplied by the direct source/ATS item.' if authoritative_direct_company else '')
    if company and is_blacklisted_url(search_url, scope='opportunities', company=company):
        _reject('blacklisted_company')
        return None,False
    remote_text=(result.get('remote_text') or '')[:220]
    provenance=result.get('_provenance') or [{'source':source.name if source else '', 'query':query, 'url':search_url}]
    is_forum_result=bool(result.get('_forum_source') or result.get('_source_category_override')=='forum' or getattr(source,'source_type','')=='forum')

    # Cloud Web community qualification deliberately produces a Hidden Lead review rather
    # than pretending the forum post is a canonical vacancy. Persist it before the normal
    # Cloud opportunity hard gates (remote status / exact job URL), and do not invoke Local AI.
    cloud_signal_review=result.get('_cloud_community_signal_review') if isinstance(result.get('_cloud_community_signal_review'),dict) else None
    if result.get('_cloud_community_signal') and cloud_signal_review:
        page_text=str(result.get('_page_text') or search_snippet or '')[:45000]
        try:
            _capture_community_hiring_signal(
                campaign,source,search_url,search_title,page_text,result,lead_collector,
                http_status=result.get('_http_status'),check_error=result.get('_check_error',''),
                local_review=cloud_signal_review,
                grounded={'accepted':True,'matches':result.get('_matched_profile_terms') or [],'reason':'Cloud Web verified community hiring signal.'},
            )
        except Exception as exc:
            UsageMetric.objects.create(category='community_signal',provider=source.name if source else '',stage='cloud_signal_persistence_error',requests=1,pages=1,errors=1,metadata={'url':search_url,'error':str(exc)[:500]})
            _reject('cloud_community_signal_error')
            return None,False
        UsageMetric.objects.create(category='community_signal',provider=source.name if source else '',stage='cloud_signal_to_hidden_lead',requests=1,pages=1,metadata={'url':search_url,'company':cloud_signal_review.get('company_name',''),'confidence':cloud_signal_review.get('confidence',0)})
        _reject('cloud_community_to_lead')
        return None,False

    # Local AI Discovery results are discovery pointers, so resolve/fetch their target.
    # A cloud-native result is already grounded research and carries structured evidence;
    # avoid immediately downloading every URL again unless a later explicit refresh asks.
    cloud_native=bool(result.get('cloud_discovery'))
    if cloud_native:
        # Defence in depth: Cloud Web must persist only a concrete opportunity with
        # verified remote eligibility. Model prompt compliance alone is not sufficient.
        remote_status=str(result.get('remote_status') or 'unknown').strip().lower()
        try: remote_confidence=int(result.get('remote_confidence') or result.get('confidence') or 0)
        except Exception: remote_confidence=0
        if remote_status not in {'fully_remote','remote'} or remote_confidence < 60:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='cloud_remote_rejected',requests=1,pages=1,metadata={'url':search_url,'remote_status':remote_status,'remote_confidence':remote_confidence})
            _reject('remote_ineligible')
            return None,False
        current_status=str(result.get('current_status') or '').strip().lower()
        if any(marker in current_status for marker in ('closed','expired','inactive','filled','cancelled','canceled','not accepting')):
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='cloud_closed_rejected',requests=1,pages=1,metadata={'url':search_url,'current_status':current_status})
            _reject('closed_or_expired')
            return None,False
        if not looks_like_specific_opportunity_url(search_url):
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='cloud_generic_url_rejected',requests=1,pages=1,metadata={'url':search_url,'reason':'exact_item_url_required'})
            _reject('generic_url')
            return None,False
        # Raw Text must be the actual directly fetched website content, never a Cloud
        # summary/evidence fallback. Cloud verification may still establish eligibility
        # when a site blocks direct retrieval; in that case description remains blank and
        # the fetch error is shown to the reviewer.
        page_text=str(result.get('_page_text') or '')
        page_html=str(result.get('_page_html') or '')
        page_ok=bool(result.get('_page_ok'))
        fetched={}
        if not result.get('_inspected_url') and not page_ok:
            fetched=fetch_target(search_url,search_title,'',timeout=15)
            page_text=str(fetched.get('text') or '')
            page_html=str(fetched.get('html') or '')
            page_ok=bool(fetched.get('ok'))
            result['_page_text']=page_text; result['_page_html']=page_html; result['_page_ok']=page_ok
            result['_inspection_error']=str(fetched.get('error') or '')[:500]
            result['_http_status']=fetched.get('http_status')
            if fetched.get('target_url'): result['_inspected_url']=fetched.get('target_url')
        inspected={
            'ok':True,  # Cloud verification is authoritative for persistence eligibility.
            'page_access_ok':page_ok,
            'target_url':result.get('_inspected_url') or search_url,
            'title':result.get('_page_title') or search_title,
            'text':page_text,'html':page_html,'bytes':0,'content_type':'text/html' if page_ok else '',
            'is_pdf':False,'language_code':'','has_jobposting_schema':False,
            'jobposting_company':str(fetched.get('jobposting_company') or ''),
            'error':str(result.get('_inspection_error') or result.get('_check_error') or ''),
            'http_status':result.get('_http_status'),
            'terminal_not_found':int(result.get('_http_status') or 0) in (404,410),
        }
    else:
        inspected=fetch_target(search_url,search_title,search_snippet)
        # A direct API/feed/community item is itself source content, not a search-engine
        # snippet. If the linked page blocks automated retrieval (for example HTTP 403),
        # retain the current source item and let the local semantic gate assess its exact
        # API/feed text. Confirmed 404/410 still fails below.
        if (result.get('_direct_source') or result.get('_structured_signal_evidence')) and not inspected.get('ok') and int(inspected.get('http_status') or 0) not in (404,410) and len(str(search_snippet or '').strip())>=80:
            inspected=dict(inspected)
            inspected['ok']=True; inspected['page_access_ok']=False
            inspected['text']=str(search_snippet or '')[:45000]
            inspected['title']=search_title
            inspected['direct_source_content']=bool(result.get('_direct_source'))
            inspected['structured_signal_content']=bool(result.get('_structured_signal_evidence'))
            # A community/news snippet can prove a hiring signal but cannot prove a vacancy
            # when the destination itself could not be fetched.
            if community_signal:
                result['_signal_only']=True
    target_url=unwrap_search_result_url((inspected.get('target_url') or search_url).strip())
    # Structured JobPosting employer identity is scoped to the current listing and
    # outranks body/related-card guesses. Re-run blacklist matching immediately after
    # the correction so a blocked employer cannot survive under a contaminated name.
    structured_company=' '.join(str(inspected.get('jobposting_company') or '').split()).strip()[:220]
    if structured_company and is_plausible_company_name(structured_company) and not authoritative_direct_company:
        company=structured_company
        company_identity_source='jobposting_schema'
        company_identity_confidence=98
        company_identity_reason='Employer identity came from structured JobPosting data on the target role.'
    if not cloud_native and followup_collector is not None and int(followup_depth or 0) < int(followup_collector.get('max_depth') or 0):
        _collect_followup_links(inspected,parent_url=target_url,source=source,query=query,depth=followup_depth,collector=followup_collector,inherited_matches=result.get('_matched_profile_terms') or [])
    if is_search_engine_url(target_url):
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='target_validation',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':'search_engine_target'})
        _reject('search_engine_target')
        return None,False
    if is_disallowed_adult_url(target_url):
        _reject('adult_content')
        return None,False
    if is_blacklisted_url(target_url, scope='opportunities', company=company):
        _reject('blacklisted_company' if company else 'blacklisted_url')
        return None,False
    specific_opportunity_url=looks_like_specific_opportunity_url(target_url)
    if not specific_opportunity_url and not result.get('_followup_source') and not community_signal:
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='generic_opportunity_url_rejected',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':'item_level_opportunity_url_required'})
        _reject('generic_url')
        return None,False
    # Never persist a search-engine click URL as provenance once the destination is
    # known. This fixes records whose Source/Target URL previously showed bing.com.
    if is_search_engine_url(search_url):
        search_url=target_url
    if inspected.get('terminal_not_found') or int(inspected.get('http_status') or 0) in (404,410):
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='target_validation',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':'confirmed_not_found','http_status':inspected.get('http_status')})
        _reject('dead_url')
        return None,False
    # Search-result snippets are discovery hints, not page content. If the target cannot
    # currently be fetched, leave it for a later run instead of creating a phantom role.
    if not inspected.get('ok'):
        # Optional SearchAPI AI research is a last-resort *research* tool, never a normal
        # classifier. Use it only for a blocked/temporarily inaccessible listing and only
        # when no direct OpenAI/Gemini/OpenRouter credential is available (the research
        # router enforces that preference). Any replacement URL must independently pass
        # ScoutBox's exact-role/employer validation before it can replace the blocked page.
        rescued=None
        blocked_status=int(inspected.get('http_status') or 0)
        if not cloud_native and blocked_status in (0,401,403,408,409,425,429,500,502,503,504):
            market=MARKET_BY_CODE.get(str(result.get('_discovery_market_code') or '').strip().lower())
            if market is not None:
                research_query=(
                    f'Find the current official employer or ATS vacancy for the role "{search_title[:180]}"'
                    + (f' at "{company[:120]}"' if company else '')
                    + f'. The discovered listing {target_url[:700]} is inaccessible. Return current public sources for the same exact role.'
                )[:3500]
                try:
                    research=searchapi_research(research_query,market=market,purpose='blocked_listing_rescue',automatic=True,limit=6)
                    for reference in research.get('results') or []:
                        ref_url=str(reference.get('url') or '').strip()
                        if not ref_url or canonical(ref_url)==canonical(target_url):
                            continue
                        candidate=_direct_role_candidate(
                            search_title,company,target_url,ref_url,
                            hit_title=str(reference.get('title') or ''),snippet=str(reference.get('snippet') or ''),
                            provider='SearchAPI AI Research',query=research_query,
                        )
                        if candidate:
                            rescued=candidate; break
                except Exception:
                    rescued=None
        if rescued:
            inspected=dict(rescued.get('fetched') or {})
            target_url=unwrap_search_result_url(str(rescued.get('url') or inspected.get('target_url') or target_url))
            search_url=target_url
            result['_searchapi_research_rescue']=True
            result['_acquisition_path']=(str(result.get('_acquisition_path') or '')+' → SearchAPI AI research rescue').strip(' →')
        else:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='target_validation',requests=1,pages=1,errors=1,metadata={'url':target_url,'search_url':search_url,'reason':'target_fetch_failed','error':inspected.get('error','')[:500]})
            _reject('target_fetch_failed')
            return None,False
    page_title=clean_placeholder(inspected.get('title'))
    dirty_search_title=search_title_contaminated(search_title,getattr(source,'name',''))
    title=(page_title if dirty_search_title and page_title else search_title) if search_title and search_title!='Untitled opportunity' else (page_title or 'Untitled opportunity')
    title,salary_title_evidence=normalize_opportunity_title(title)
    title=title[:300] or 'Untitled opportunity'
    if salary_title_evidence: result['_title_salary_evidence']=salary_title_evidence
    page_text=(inspected.get('text') or '').strip()
    if result.get('_direct_source') and str(search_snippet or '').strip():
        page_text=str(search_snippet or '').strip()[:45000]
    # Preserve high-confidence evidence from a third-party board before an exact employer/ATS
    # resolver replaces the working page. This is important for boards that expose an explicit
    # posted date or remote-location restriction more clearly than the employer shell.
    original_job_board_url=target_url if _is_third_party_job_url(target_url) else ''
    original_board_evidence={}
    if original_job_board_url:
        board_signal=explicit_post_date_signal(
            page_text, schema_date=str(inspected.get('jobposting_date_posted') or ''), final_url=original_job_board_url
        )
        board_remote=normalize_remote_constraints(
            page_text+' '+str(inspected.get('jobposting_location') or ''),
            (remote_text if result.get('_direct_source') else ''),
        )
        board_role_location=(str(result.get('_role_location_hint') or '').strip() if result.get('_direct_source') else '') or extract_role_location(page_text, inspected.get('jobposting_location') or '')
        original_board_evidence={
            'url':original_job_board_url[:1000],
            'title':str(page_title or title)[:300],
            'posted_date':(board_signal.get('date').isoformat() if board_signal and board_signal.get('date') else ''),
            'posted_date_note':str((board_signal or {}).get('note') or '')[:500],
            'posted_date_confidence':int((board_signal or {}).get('confidence') or 0),
            'remote':board_remote or {},
            'role_location':str(board_role_location or '')[:240],
        }
    # A non-English page is no longer discarded merely because it came from an ordinary
    # market query. If the market/detector identifies a language, create a faithful English
    # interpretation and run the exact same role/profile/remote gates on that interpretation.
    # This fixes the previous failure mode where Asian pages were successfully discovered
    # and then rejected simply because only a tiny subset of queries carried a multilingual tag.
    if not cloud_native and not primarily_english(page_text, inspected.get('language_code') or ''):
        multilingual_language,translation_source=_translation_language_for_result(result,inspected.get('language_code') or '')
        interpretation=_translate_multilingual_page(page_text,multilingual_language,target_url) if multilingual_language else ''
        if not interpretation:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='language_gate',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':'multilingual_translation_failed' if multilingual_language else 'page_not_primarily_english','language_code':inspected.get('language_code',''),'multilingual_language':multilingual_language,'translation_source':translation_source})
            _reject('multilingual_translation_failed' if multilingual_language else 'non_english')
            return None,False
        result['_original_language_text']=page_text[:45000]
        result['_english_interpretation']=interpretation[:45000]
        result['_multilingual_qualified']=True
        result['_multilingual_language']=result.get('_multilingual_language') or multilingual_language
        result['_multilingual_source']=result.get('_multilingual_source') or translation_source
        try:
            UsageMetric.objects.create(category='discovery_market',provider=source.name if source else '',stage='multilingual_page_translation',requests=1,pages=1,metadata={'url':target_url,'language_code':inspected.get('language_code',''),'multilingual_language':multilingual_language,'translation_source':translation_source,'decision':'translated_for_qualification'})
        except Exception:
            pass
        page_text=interpretation[:45000]
    if not cloud_native and community_signal:
        page_text=_searchapi_corroborate_community_signal(result,title,company,target_url,page_text)
    if (_looks_like_job_collection_title(title) or _looks_like_job_collection_title(page_title) or _aggregate_job_page(target_url,page_title or title,page_text)) and not community_signal:
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='aggregate_page_rejected',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':'multi_role_listing'})
        _reject('multi_role_page')
        return None,False
    role_gate=classify_role_page(target_url,title,page_text,has_jobposting_schema=bool(inspected.get('has_jobposting_schema')),is_pdf=bool(inspected.get('is_pdf')))
    local_review=None
    grounded=None
    if role_gate.get('hard_reject') and not community_signal:
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='hard_opportunity_source_gate',requests=1,pages=1,metadata={'url':target_url,'reason':role_gate.get('reason','')[:500]})
        _reject('invalid_opportunity_source')
        return None,False
    if cloud_native and not role_gate.get('accepted') and not role_gate.get('hard_reject') and int(result.get('confidence') or 0)>=60 and (result.get('application_process') or result.get('engagement_type') or result.get('current_status')):
        role_gate={'accepted':True,'hard_reject':False,'reason':'Accepted from grounded cloud opportunity research with explicit engagement/application evidence.','positive_signals':['cloud grounded research'],'negative_signals':role_gate.get('negative_signals',[])}

    if not cloud_native:
        # Local search-engine snippets are only pointers. Prove candidate relevance from the
        # fetched page itself using the strict primary-JD rule for every local source, not
        # only large aggregators. One isolated specialist/body keyword is insufficient.
        if search_profile:
            grounded=grounded_profile_relevance(title,page_text,search_profile,strict_market=True)
            if not grounded.get('accepted'):
                inherited=list(result.get('_matched_profile_terms') or []) if (result.get('_followup_source') or community_signal) else []
                if inherited:
                    grounded={'accepted':True,'matches':inherited,'reason':('Inherited candidate relevance from a directly linked relevant parent.' if result.get('_followup_source') else 'Community/news signal matched the candidate profile during pre-scoring.')+' Local semantic review must still qualify this page.','inherited':True}
                else:
                    UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='profile_relevance',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':grounded.get('reason',''),'matches':grounded.get('matches',[]),'strict_local':True})
                    _reject('profile_relevance')
                    return None,False
            result['_matched_profile_terms']=grounded.get('matches') or []
            result['_grounded_profile_relevance']=grounded
        else:
            grounded={'accepted':True,'matches':result.get('_matched_profile_terms') or [],'reason':'No structured search profile was available; semantic local preflight must establish relevance.'}

        # Infer a company name for local semantic qualification/corroboration when the
        # search adapter did not supply one. Persistence still uses the same reviewed value.
        if not is_plausible_company_name(company):
            try:
                recovered_company=display_company_name(company_from_page(target_url,page_title or title,page_text),target_url)[:220]
                company=recovered_company if is_plausible_company_name(recovered_company) else ''
            except Exception:
                company=''
        if not is_plausible_company_name(company):
            company=_deterministic_company_from_evidence(search_snippet,page_text,page_title,title)

        # The Ollama pre-persistence gate distinguishes a real opening/project from SEO
        # job-description pages, technical documentation, generic listings and mere topical
        # overlap BEFORE an Opportunity can be created. A model failure fails closed.
        try:
            local_review=_local_page_review(
                campaign,title,company,target_url,page_text,role_gate,grounded,
                has_jobposting_schema=bool(inspected.get('has_jobposting_schema')),
            )
            result['_local_page_review']=local_review
        except LocalAILaneBusy:
            raise
        except Exception as exc:
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_pre_persistence_gate',requests=1,pages=1,errors=1,metadata={'url':target_url,'search_url':search_url,'reason':'local_semantic_review_failed','error':str(exc)[:500]})
            _reject('local_semantic_review_failed')
            return None,False

        purpose=str(local_review.get('purpose') or 'other')
        opp_level=selectivity_current('opportunities')
        opp_policy=opportunity_thresholds(opp_level)
        campaign_ok,campaign_hits=campaign_alignment(
            campaign,local_review.get('role_title') or title,page_text,level=opp_level,kind='opportunity'
        ) if opp_policy.get('requires_campaign_anchor') else (True,[])
        semantic_opp=(
            purpose in {'job_opportunity','contract_project'} and bool(local_review.get('actionable')) and
            int(local_review.get('confidence') or 0)>=int(opp_policy['confidence']) and bool(local_review.get('profile_relevant')) and
            int(local_review.get('relevance_confidence') or 0)>=int(opp_policy['relevance_confidence']) and
            int(local_review.get('fit_score') or 0)>=int(opp_policy.get('fit_score') or 0) and campaign_ok
        )
        result['_opportunity_selectivity']={'level':opp_level,'policy':opp_policy,'campaign_hits':campaign_hits}
        semantic_lead=(
            purpose in {'company_hiring_signal','company_outreach_target'} and bool(local_review.get('lead_actionable')) and
            int(local_review.get('confidence') or 0)>=60
        )
        direct_role=' '.join(str(local_review.get('role_title') or '').split()).strip()
        reviewed_company=' '.join(str(local_review.get('company_name') or '').split()).strip()
        if result.get('_direct_source') and direct_role and 4 <= len(direct_role) <= 180 and _ROLE_WORDS.search(direct_role):
            title,_removed_salary=normalize_opportunity_title(direct_role); title=title[:300]
            if _removed_salary and not result.get('_title_salary_evidence'): result['_title_salary_evidence']=_removed_salary
        # Local AI may fill a genuinely missing employer, but it must never replace a
        # trustworthy direct-source/ATS identity or structured JobPosting employer. This
        # prevents JD headings such as "What we" from poisoning company identity.
        if (reviewed_company and is_plausible_company_name(reviewed_company)
                and not structured_company and not authoritative_direct_company):
            company=reviewed_company[:220]
            company_identity_source='local_ai'
            try: company_identity_confidence=max(0,min(100,int(local_review.get('company_confidence') or local_review.get('confidence') or 60)))
            except Exception: company_identity_confidence=60
            company_identity_reason=str(local_review.get('company_reason') or 'Employer filled from Local AI page review.')[:800]
        if not is_plausible_company_name(company):
            company=''
            try:
                recovered_company=display_company_name(company_from_page(target_url,page_title or title,page_text),target_url)[:220]
                if is_plausible_company_name(recovered_company):
                    company=recovered_company
                    company_identity_source='page_identity'
                    company_identity_confidence=78
                    company_identity_reason='Employer recovered from target-page identity evidence.'
            except Exception:
                pass
        if not is_plausible_company_name(company):
            company=_deterministic_company_from_evidence(search_snippet,page_text,page_title,title)
            if is_plausible_company_name(company):
                company_identity_source='deterministic_page_evidence'
                company_identity_confidence=68
                company_identity_reason='Employer recovered from deterministic retained page evidence.'
        # Generic community discussions and structured signal snippets are evidence of
        # hiring, not vacancy URLs. A fetched forum post may still become an Opportunity
        # when it is a concrete item-level role; otherwise downgrade it to a Hidden Lead.
        signal_only=bool(result.get('_signal_only') or result.get('_news_signal'))
        if semantic_opp and (not specific_opportunity_url or signal_only):
            semantic_opp=False
            semantic_lead=semantic_lead or (
                bool(local_review.get('profile_relevant')) and int(local_review.get('confidence') or 0)>=60 and
                int(local_review.get('relevance_confidence') or 0)>=55 and bool(local_review.get('actionable') or local_review.get('lead_actionable'))
            )
            if semantic_lead and purpose in {'job_opportunity','contract_project'}:
                local_review=dict(local_review); local_review['purpose']='company_hiring_signal'; local_review['lead_actionable']=True
        elif community_signal and not semantic_opp and purpose in {'job_opportunity','contract_project'}:
            # A relevant hiring post can be useful outreach evidence even when it misses
            # the stricter Opportunity fit/selectivity threshold.
            semantic_lead=(
                bool(local_review.get('profile_relevant')) and int(local_review.get('confidence') or 0)>=60 and
                int(local_review.get('relevance_confidence') or 0)>=55 and bool(local_review.get('actionable'))
            )
            if semantic_lead:
                local_review=dict(local_review); local_review['purpose']='company_hiring_signal'; local_review['lead_actionable']=True
        if not semantic_opp:
            if semantic_lead:
                try:
                    if community_signal:
                        _capture_community_hiring_signal(campaign,source,target_url,page_title or title,page_text,result,lead_collector,http_status=inspected.get('http_status'),check_error=inspected.get('error',''),local_review=local_review,grounded=grounded)
                    else:
                        _capture_campaign_lead(campaign,source,target_url,page_title or title,page_text,result,lead_collector,http_status=inspected.get('http_status'),check_error=inspected.get('error',''),local_review=local_review,grounded=grounded)
                except Exception:
                    pass
                UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_page_purpose',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'purpose':purpose,'confidence':local_review.get('confidence'),'disposition':'hidden_lead','community_signal':community_signal})
                _reject('local_semantic_to_lead')
                return None,False
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_page_purpose',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'purpose':purpose,'confidence':local_review.get('confidence'),'reason':local_review.get('reason'),'disposition':'discard'})
            _reject('local_non_opportunity')
            return None,False

        # Prefer an exact employer-hosted copy over a third-party/community listing when
        # Local discovery can verify the same role. Validation is URL/content-bound: the
        # semantic approval of the original board page is NEVER inherited by a replacement.
        # If replacement validation cannot complete, retain the already verified board page.
        if original_job_board_url:
            preferred=_prefer_exact_employer_role(title,company,original_job_board_url)
            if preferred:
                direct=preferred.get('fetched') or {}
                candidate_url=str(preferred.get('url') or '')
                candidate_title=clean_placeholder(direct.get('title')) or page_title
                candidate_text=(direct.get('text') or '').strip()
                candidate_gate=classify_role_page(candidate_url,candidate_title or title,candidate_text,has_jobposting_schema=bool(direct.get('has_jobposting_schema')),is_pdf=bool(direct.get('is_pdf')))
                candidate_validation=_replacement_role_page_valid(title,company,candidate_url,direct)
                candidate_review=None; replacement_ok=False; replacement_reason=str(candidate_validation.get('reason') or '')
                if candidate_validation.get('accepted'):
                    try:
                        candidate_review=_local_page_review(
                            campaign,title,company,candidate_url,candidate_text,candidate_gate,grounded,
                            has_jobposting_schema=bool(direct.get('has_jobposting_schema')),
                        )
                        candidate_purpose=str(candidate_review.get('purpose') or 'other')
                        replacement_specialist_ok=True
                        if opp_policy.get('requires_campaign_anchor'):
                            replacement_specialist_ok,_replacement_hits=campaign_alignment(campaign,candidate_review.get('role_title') or candidate_title,candidate_text,level=opp_level,kind='opportunity')
                        replacement_ok=(
                            candidate_purpose in {'job_opportunity','contract_project'} and
                            bool(candidate_review.get('actionable')) and int(candidate_review.get('confidence') or 0)>=int(opp_policy['confidence']) and
                            bool(candidate_review.get('profile_relevant')) and int(candidate_review.get('relevance_confidence') or 0)>=int(opp_policy['relevance_confidence']) and
                            int(candidate_review.get('fit_score') or 0)>=int(opp_policy.get('fit_score') or 0) and replacement_specialist_ok
                        )
                        if not replacement_ok:
                            replacement_reason='replacement failed independent Local AI opportunity/relevance validation'
                    except LocalAILaneBusy:
                        replacement_reason='replacement validation deferred because Local AI lane is busy'
                    except Exception as exc:
                        replacement_reason='replacement semantic validation failed: '+str(exc)[:300]
                if replacement_ok:
                    target_url=candidate_url; inspected=direct; page_title=candidate_title; page_text=candidate_text
                    role_gate=candidate_gate; local_review=candidate_review; purpose=str(local_review.get('purpose') or 'job_opportunity')
                    result['_local_page_review']=local_review
                    provenance=_merge_provenance(provenance,[{'source':'Employer exact-role resolver','query':preferred.get('query',''),'url':target_url,'provider':preferred.get('provider',''),'original_job_board_url':original_job_board_url,'independently_revalidated':True}])
                    result['_preferred_employer_url']=target_url
                else:
                    # Keep the original verified vacancy and record why the tempting
                    # replacement was discarded. This closes the JobsDB -> unrelated
                    # Coursera/article substitution class of corruption.
                    result['_preferred_employer_rejected_url']=candidate_url[:1000]
                    result['_preferred_employer_rejected_reason']=replacement_reason[:600]
                    UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='employer_role_replacement_rejected',requests=1,pages=1,metadata={'url':candidate_url,'original_job_board_url':original_job_board_url,'reason':replacement_reason[:500]})
            result['_original_job_board_url']=original_job_board_url
        if original_job_board_url:
            provenance=_merge_provenance(provenance,[{'source':'Original job-board discovery','query':query,'url':original_job_board_url,'original_job_board_url':original_job_board_url}])
            marker_line='Original job board URL: '+original_job_board_url
            if marker_line.casefold() not in page_text.casefold():
                page_text=(page_text.rstrip()+'\n\n'+marker_line).strip()

        # A legitimate local model classification may recover an unconventional vacancy
        # that the deterministic role gate missed, but only with explicit semantic evidence.
        if not role_gate.get('accepted') and not role_gate.get('hard_reject'):
            role_gate={
                'accepted':True,'hard_reject':False,'score':role_gate.get('score',0),
                'reason':'Local Ollama pre-persistence review verified a concrete actionable work opportunity.',
                'positive_signals':list(dict.fromkeys(list(role_gate.get('positive_signals') or [])+['local semantic opportunity verification']))[:8],
                'negative_signals':role_gate.get('negative_signals',[]),
            }

        # "Job description", responsibilities and qualifications alone are not strong
        # vacancy evidence. Ambiguous pages require a second local search-provider result
        # that points to a separate concrete employer/ATS job item.
        structural=local_review.get('structural_actionability') or _local_action_signals(target_url,page_text,has_jobposting_schema=bool(inspected.get('has_jobposting_schema')))
        # A current item acquired from a first-party API/feed/ATS/community adapter has
        # already bypassed search-engine cache uncertainty. Once the local semantic gate
        # verifies that exact item as a concrete actionable role, do not require a second
        # search-engine corroboration result merely because the host page lacks ATS markup.
        if not structural.get('clear') and not result.get('_direct_source'):
            corroboration=_local_corroborate_candidate(source,title,company,target_url)
            result['_local_corroboration']=corroboration
            if not corroboration.get('corroborated'):
                # A useful organization can still become a Hidden Lead if the model says
                # direct outreach is actionable; the ambiguous page itself never becomes
                # an Opportunity merely because it contains role keywords.
                if bool(local_review.get('lead_actionable')):
                    try:
                        lead_review=dict(local_review); lead_review['purpose']='company_outreach_target'
                        _capture_campaign_lead(campaign,source,target_url,page_title or title,page_text,result,lead_collector,http_status=inspected.get('http_status'),check_error=inspected.get('error',''),local_review=lead_review,grounded=grounded)
                    except Exception:
                        pass
                UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='local_opportunity_corroboration',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':corroboration.get('reason'),'purpose':purpose})
                _reject('local_uncorroborated_opportunity')
                return None,False
    else:
        # Preserve Cloud Web behavior exactly: its own grounded research/resolver remains
        # authoritative and does not pass through any of the Local Ollama gates above.
        if not role_gate.get('accepted'):
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='role_gate',requests=1,pages=1,metadata={'url':target_url,'search_url':search_url,'reason':role_gate.get('reason',''),'signals':role_gate})
            try:
                _capture_campaign_lead(campaign,source,target_url,page_title or title,page_text,result,lead_collector,http_status=inspected.get('http_status'),check_error=inspected.get('error',''))
            except Exception:
                pass
            _reject('role_gate')
            return None,False

    if cloud_native and original_job_board_url:
        result['_original_job_board_url']=original_job_board_url
        provenance=_merge_provenance(provenance,[{'source':'Original job-board discovery','query':query,'url':original_job_board_url,'original_job_board_url':original_job_board_url}])
        marker_line='Original job board URL: '+original_job_board_url
        if marker_line.casefold() not in page_text.casefold():
            page_text=(page_text.rstrip()+'\n\n'+marker_line).strip()

    # Final employer sanity check after any exact-role resolver.  A job board/ATS may
    # host the page, but it must never become Opportunity.company.  Recover the employer
    # deterministically from the fetched page when possible; otherwise leave it blank.
    if not is_plausible_company_name(company):
        try:
            recovered=display_company_name(company_from_page(target_url,page_title or title,page_text),target_url)[:220]
        except Exception:
            recovered=''
        company=recovered if is_plausible_company_name(recovered) else ''

    can=canonical(target_url)
    if _recycled_opportunity_match(title,company,target_url,page_text):
        st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate()); st.duplicates+=1; st.save(update_fields=['duplicates'])
        if lead_collector is not None: lead_collector['duplicates']=int(lead_collector.get('duplicates') or 0)+1
        _reject('recycled_or_duplicate')
        return None,False
    applied=_applied_match(title,company,target_url)
    if applied:
        st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate()); st.applied_matches+=1; st.save(update_fields=['applied_matches'])
        applied.opportunity.last_seen=now
        facts=applied.opportunity.extracted_facts or {}
        facts['discovery_provenance']=_merge_provenance(facts.get('discovery_provenance',[]),provenance)
        facts['rediscovered_profile_matches']=result.get('_matched_profile_terms',[])
        if result.get('_glassdoor_attribution_required'): facts['glassdoor_attribution_required']=True
        if result.get('_direct_source'):
            facts['acquisition']={
                'path':str(result.get('_acquisition_path') or 'Direct source')[:80],
                'adapter':str(result.get('_direct_adapter') or '')[:80],
                'source_item_id':str(result.get('_direct_item_id') or '')[:160],
                'published_at':str(result.get('published_at') or '')[:80],
                'source_last_seen':timezone.now().isoformat(),'current_source_listing':True,
            }
        applied.opportunity.extracted_facts=facts
        applied.opportunity.search_url=search_url; applied.opportunity.target_url=target_url
        applied.opportunity.save(update_fields=['last_seen','search_url','target_url','extracted_facts','updated_at'])
        attribute_campaign(applied.opportunity,campaign)
        return applied.opportunity,False

    recent_cutoff=now-timezone.timedelta(days=cfg.duplicate_window_days)
    # Catch URL spelling variants (for example kernel-developer vs kernel_developer) and
    # same-company/same-role rediscoveries before a second visible row is persisted.
    dup=active_duplicate_opportunity(title,company,target_url,days=max(90,int(cfg.duplicate_window_days or 90)))
    if not dup:
        dup=Opportunity.objects.filter(user_deleted=False,canonical_url=can,first_seen_by_portal__gte=recent_cutoff).first()
    # Do not merge on title/body similarity here. The later role-family pass has the
    # resolved employer, explicit requisition IDs, role location and responsibilities and
    # can therefore distinguish same-titled vacancies safely across providers.
    if dup:
        dup.last_seen=now; attribute_campaign(dup,campaign)
        facts=dup.extracted_facts or {}
        facts['rediscovered_query']=query
        facts['discovery_provenance']=_merge_provenance(facts.get('discovery_provenance',[]),provenance)
        facts['rediscovered_profile_matches']=result.get('_matched_profile_terms',[])
        if result.get('_glassdoor_attribution_required'): facts['glassdoor_attribution_required']=True
        if result.get('_direct_source'):
            facts['acquisition']={
                'path':str(result.get('_acquisition_path') or 'Direct source')[:80],
                'adapter':str(result.get('_direct_adapter') or '')[:80],
                'source_item_id':str(result.get('_direct_item_id') or '')[:160],
                'published_at':str(result.get('published_at') or '')[:80],
                'source_last_seen':timezone.now().isoformat(),'current_source_listing':True,
            }
            if result.get('_community_thread_url'): facts['acquisition']['community_thread_url']=str(result.get('_community_thread_url'))[:1000]
            if result.get('_ats_board'): facts['acquisition']['ats_board']=str(result.get('_ats_board'))[:160]
            if result.get('_role_location_hint'):
                facts['direct_role_location_hint']=str(result.get('_role_location_hint'))[:800]
            if is_forum_result:
                facts['acquisition']['source_category']='forum'
                facts['forum']={
                    'name':str(result.get('_forum_name') or (source.name if source else ''))[:160],
                    'post_date':str(result.get('_forum_post_date') or result.get('published_at') or '')[:80],
                    'post_id':str(result.get('_forum_post_id') or result.get('_direct_item_id') or '')[:160],
                    'software':str(result.get('_forum_software') or '')[:80],
                    'query':str(result.get('_forum_query') or query or '')[:300],
                    'url':target_url[:1000],
                    'age_policy':'specific forum post date unless stronger opportunity-date evidence exists',
                }
        _uctx=usage_context()
        facts['campaign_id']=_uctx.get('campaign_id') or campaign.pk
        if _uctx.get('campaign_run_id'): facts['campaign_run_id']=_uctx.get('campaign_run_id')
        dup.extracted_facts=facts; dup.search_url=search_url; dup.target_url=target_url
        dup_updates=['last_seen','search_url','target_url','extracted_facts','updated_at']
        if result.get('cloud_discovery') and dup.status in {'new','unknown'}:
            dup.status=_cloud_recommendation_status(result); dup_updates.append('status')
        location_resolution=resolve_opportunity_location(
            target_url=target_url, inspected=inspected, page_title=page_title or title, page_text=page_text,
            direct_location_hint=result.get('_role_location_hint') or facts.get('direct_role_location_hint') or '',
            market_location_hint=result.get('_market_location_hint') or '',
            stored_role_location=dup.role_location, remote_text=dup.remote_text or result.get('remote_text') or '',
            company_intel=dup.company_intel, facts=facts,
        )
        detected_country=str(location_resolution.get('country') or '').strip()[:120]
        detected_role_location=str(location_resolution.get('role_location') or '').strip()[:240]
        detected_locations=normalize_location_items(location_resolution.get('locations') or detected_country, source='role_location', evidence=detected_role_location or detected_country)
        facts['country_provenance']=location_resolution.get('provenance') or {}
        dup.extracted_facts=facts
        if hasattr(dup,'locations') and detected_locations and detected_locations != normalize_location_items(getattr(dup,'locations',None)):
            dup.locations=detected_locations; dup_updates.append('locations')
        if detected_country and detected_country != str(dup.country or '').strip():
            dup.country=detected_country; dup_updates.append('country')
        if detected_role_location and detected_role_location != str(dup.role_location or '').strip():
            dup.role_location=detected_role_location; dup_updates.append('role_location')
        if not dup.contact_email:
            _email=_best_discovery_contact_email(result,page_text,search_snippet,company,target_url,cloud_native=cloud_native)
            if _email:
                dup.contact_email=_email; dup_updates.append('contact_email')
        if cloud_native and not dup.note:
            signal=_distinctive_cloud_note(result)
            if signal: dup.note=signal; dup_updates.append('note')
        if not str(dup.list_highlight or '').strip():
            rebuilt=(opportunity_specific_highlight(dup,result=result,title=dup.title,description=dup.description or dup.raw_search_snippet,facts=facts,remote_text=dup.remote_text) if cloud_native else derive_opportunity_highlight(opportunity=dup,title=dup.title,description=dup.description or dup.raw_search_snippet,facts=facts,remote_text=dup.remote_text))
            if rebuilt:
                dup.list_highlight=rebuilt[:600]; dup_updates.append('list_highlight')
        # Salary extraction is deliberately non-blocking for Local Discovery: local runs
        # only parse evidence already in memory. Cloud runs reuse Gemini/provider salary
        # fields from the same research response and never launch a second model call here.
        salary_info=(salary_from_retained_opportunity(dup) or salary_from_cloud_result(result,target_url)) if cloud_native else salary_from_retained_opportunity(dup)
        if salary_info:
            for _field,_value in salary_info.items():
                if hasattr(dup,_field) and _value not in (None,''):
                    setattr(dup,_field,_value); dup_updates.append(_field)
        dup.save(update_fields=list(dict.fromkeys(dup_updates)))
        if result.get('_publication_authoritative') and result.get('published_at'):
            try:
                OpportunityEvidence.objects.update_or_create(
                    opportunity=dup,kind='search_or_source_date',label=('Forum post date' if is_forum_result else 'Direct source publication date'),source_url=target_url,
                    defaults={'value':result.get('published_at'),'confidence':96,'metadata':{'authoritative_source_timestamp':True,'forum_post_timestamp':bool(is_forum_result),'used_for_post_age':bool(is_forum_result)}},
                )
                if cloud_native: apply_cloud_post_age(dup,result)
                else: recompute(dup)
            except Exception:
                pass
        try:
            promote_record_contact_to_addressbook(
                dup,source=('Cloud Web Opportunity' if cloud_native else 'Source-guided Opportunity'),source_url=target_url,
                texts=(page_text,page_title,search_snippet),confidence=(88 if cloud_native else 78),queue_research=False,
            )
        except Exception:
            pass
        st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate()); st.duplicates+=1; st.save(update_fields=['duplicates'])
        if lead_collector is not None: lead_collector['duplicates']=int(lead_collector.get('duplicates') or 0)+1
        return dup,False

    # Local AI Discovery campaign discovery is local-only. Cloud research is never
    # injected through stage routing while a Local AI Discovery run context is active.

    pre_score=max(0,min(100,int((local_review or {}).get('fit_score') if local_review else result.get('_pre_score',45))))
    if inspected.get('is_pdf'): pre_score=max(0,pre_score-18)
    language=(inspected.get('language_code') or '')[:16]
    language_delta=preferred_language_delta(Profile.objects.get_or_create(pk=1)[0],language)
    if language_delta: pre_score=max(0,min(100,pre_score+language_delta))
    _uctx=usage_context()
    current_remote=normalize_remote_constraints(
        page_text+' '+str(inspected.get('jobposting_location') or ''),
        (remote_text if result.get('_direct_source') else ''),
    )
    board_remote=(original_board_evidence.get('remote') if isinstance(original_board_evidence,dict) else {}) or {}
    remote_evidence=remote_work_evidence(
        page_text+' '+str(inspected.get('jobposting_location') or ''),remote_text,page_title or title,
        structured_remote=bool(result.get('_direct_source')),
    )
    arrangement_evidence=work_arrangement_evidence(
        page_text+' '+str(inspected.get('jobposting_location') or ''),remote_text,page_title or title,
        structured_remote=bool(result.get('_direct_source')),
    )
    # A structured country restriction from the original board outranks a generic worldwide
    # label on a replacement employer shell; an explicit employer restriction still wins.
    if current_remote and current_remote.get('country'):
        deterministic_remote=current_remote
    elif board_remote and board_remote.get('country'):
        deterministic_remote=board_remote
    else:
        deterministic_remote=current_remote or board_remote or None
    # Any positive Remote/Hybrid/On-site badge must be grounded in explicit role-level
    # working-arrangement evidence. This prevents semantic guesses such as "growing your
    # career" or benefit wording from becoming Hybrid, while still trusting direct-source
    # structured workplace metadata and explicit page wording.
    if not deterministic_remote and arrangement_evidence.get('confirmed'):
        deterministic_remote={
            'status':str(arrangement_evidence.get('status') or 'unknown'),
            'label':str(arrangement_evidence.get('label') or 'Unknown'),
            'country':'','countries':[],
            'confidence':int(arrangement_evidence.get('confidence') or 90),
            'reason':str(arrangement_evidence.get('reason') or 'Fetched page explicitly describes the working arrangement.'),
        }
    if deterministic_remote:
        result['remote_status']=deterministic_remote['status']
        result['remote_label']=deterministic_remote['label']
        result['remote_confidence']=deterministic_remote['confidence']
        result['remote_reason']=deterministic_remote['reason']
        if deterministic_remote.get('country'):
            result['country']=deterministic_remote['country']
        remote_text=deterministic_remote['label'][:220]
        if local_review:
            local_review=dict(local_review)
            local_review.update({'remote_status':deterministic_remote['status'],'remote_label':deterministic_remote['label'],
                                 'remote_confidence':deterministic_remote['confidence'],'remote_reason':deterministic_remote['reason']})
    else:
        claimed_status=str((result if cloud_native else (local_review or {})).get('remote_status') or '').strip().lower()
        if claimed_status in {'fully_remote','remote','hybrid','onsite'}:
            grounded_reason=str(arrangement_evidence.get('reason') or 'No explicit role-level remote/hybrid/on-site working-arrangement evidence found.')[:1200]
            if cloud_native:
                result['remote_status']='unknown'; result['remote_label']='Unknown'
                result['remote_confidence']=min(40,int(result.get('remote_confidence') or 0))
                result['remote_reason']=grounded_reason
            elif local_review:
                local_review=dict(local_review)
                local_review.update({
                    'remote_status':'unknown','remote_label':'Unknown',
                    'remote_confidence':min(40,int(local_review.get('remote_confidence') or 0)),
                    'remote_reason':grounded_reason,
                })
                result['_local_page_review']=local_review
    facts={
        'discovery_query':query,
        'campaign_id':_uctx.get('campaign_id') or campaign.pk,
        'campaign_run_id':_uctx.get('campaign_run_id'),
        'discovery_provenance':provenance,
        'raw_search_hits_consolidated':int(result.get('_raw_hits',1)),
        'cv_profile_matches':result.get('_matched_profile_terms',[]),
        'grounded_profile_relevance':result.get('_grounded_profile_relevance') or {},
        'search_pre_score':pre_score,
        'preferred_language_delta':language_delta,
        'facebook_mode':result.get('facebook_mode',''),
        'cloud_discovery':bool(result.get('cloud_discovery')),
        'cloud_discovery_provider':result.get('cloud_provider',''),
        'cloud_discovery_model':result.get('cloud_model',''),
        'discovery_market':str(result.get('_discovery_market') or '')[:120],
        'discovery_market_code':str(result.get('_discovery_market_code') or '')[:40],
        'multilingual_language':str(result.get('_multilingual_language') or '')[:40],
        'multilingual_source':str(result.get('_multilingual_source') or '')[:20],
        'multilingual_qualified':bool(result.get('_multilingual_qualified')),
        'original_language_text':str(result.get('_original_language_text') or '')[:45000],
        'english_interpretation':str(result.get('_english_interpretation') or '')[:45000],
        'glassdoor_attribution_required':bool(result.get('_glassdoor_attribution_required')),
        'role_page_classification':role_gate,
        'remote_classification': ({
            'status': str(result.get('remote_status') or 'unknown').strip().lower() if str(result.get('remote_status') or '').strip().lower() in {'fully_remote','remote','hybrid','onsite','unknown'} else 'unknown',
            'label': str(result.get('remote_label') or {'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}.get(str(result.get('remote_status') or 'unknown').strip().lower(),'Unknown'))[:60],
            'confidence': max(0,min(100,int(result.get('remote_confidence') or result.get('confidence') or 0))),
            'reason': str(result.get('remote_reason') or result.get('remote_text') or '')[:1200],
            'source': 'Cloud AI classification',
        } if cloud_native else ({
            'status':str((local_review or {}).get('remote_status') or 'unknown'),
            'label':str((local_review or {}).get('remote_label') or 'Unknown')[:40],
            'confidence':int((local_review or {}).get('remote_confidence') or 0),
            'reason':str((local_review or {}).get('remote_reason') or '')[:1200],
            'source':'Local Ollama pre-persistence review',
        } if local_review else {})),
        'original_job_board_url':str(result.get('_original_job_board_url') or original_job_board_url or '')[:1000],
        'original_job_board_evidence':original_board_evidence,
        'preferred_employer_url':str(result.get('_preferred_employer_url') or '')[:1000],
        'page_prefetched':bool(inspected.get('page_access_ok', inspected.get('ok'))),
        'content_type':inspected.get('content_type',''),
        'is_pdf':bool(inspected.get('is_pdf')),
        'target_fetch_error':inspected.get('error',''),
    }
    if company and is_plausible_company_name(company):
        facts['company_identity']={
            'name':company,
            'source':company_identity_source or ('search_result' if result.get('company') else 'page_evidence'),
            'confidence':int(company_identity_confidence or (70 if result.get('company') else 60)),
            'reason':company_identity_reason or 'Employer identity retained from the strongest available listing evidence.',
            'authoritative':bool(authoritative_direct_company or company_identity_source=='jobposting_schema'),
        }
    if result.get('_direct_source'):
        facts['acquisition']={
            'path':str(result.get('_acquisition_path') or 'Direct source')[:80],
            'adapter':str(result.get('_direct_adapter') or '')[:80],
            'source_item_id':str(result.get('_direct_item_id') or '')[:160],
            'published_at':str(result.get('published_at') or '')[:80],
            'source_last_seen':timezone.now().isoformat(),
            'current_source_listing':True,
        }
        if result.get('_community_thread_url'):
            facts['acquisition']['community_thread_url']=str(result.get('_community_thread_url'))[:1000]
        if result.get('_ats_board'):
            facts['acquisition']['ats_board']=str(result.get('_ats_board'))[:160]
        if result.get('_role_location_hint'):
            facts['direct_role_location_hint']=str(result.get('_role_location_hint'))[:800]
    if is_forum_result:
        acq=dict(facts.get('acquisition') or {})
        acq.setdefault('path',str(result.get('_acquisition_path') or 'Forum')[:80])
        acq.setdefault('adapter',str(result.get('_direct_adapter') or '')[:80])
        acq['source_category']='forum'
        acq['published_at']=str(result.get('published_at') or result.get('_forum_post_date') or acq.get('published_at') or '')[:80]
        if result.get('_role_location_hint'):
            facts['direct_role_location_hint']=str(result.get('_role_location_hint'))[:800]
        facts['acquisition']=acq
        facts['forum']={
            'name':str(result.get('_forum_name') or (source.name if source else ''))[:160],
            'base_url':str(result.get('_forum_base_url') or getattr(source,'base_url','') or '')[:500],
            'software':str(result.get('_forum_software') or '')[:80],
            'search_path':str(result.get('_forum_search_path') or '')[:200],
            'post_date':str(result.get('_forum_post_date') or result.get('published_at') or '')[:80],
            'post_id':str(result.get('_forum_post_id') or result.get('_direct_item_id') or '')[:160],
            'query':str(result.get('_forum_query') or query or '')[:300],
            'url':target_url[:1000],
            'age_policy':'specific forum post date unless stronger opportunity-date evidence exists',
        }
    if local_review:
        direct_role_title=' '.join(str(local_review.get('role_title') or '').split()).strip()
        if result.get('_direct_source') and direct_role_title and 4 <= len(direct_role_title) <= 180 and _ROLE_WORDS.search(direct_role_title):
            title,_removed_salary=normalize_opportunity_title(direct_role_title); title=title[:300]
            if _removed_salary and not result.get('_title_salary_evidence'): result['_title_salary_evidence']=_removed_salary
        facts['local_pre_persistence_review']=local_review
        facts['fit_classification']={
            'score':int(local_review.get('fit_score') or pre_score),'confidence':int(local_review.get('fit_confidence') or 0),
            'reason':str(local_review.get('fit_reason') or '')[:1600],'recommendation':str(local_review.get('recommendation') or 'Unknown')[:80],
            'source':'Local Ollama pre-persistence review',
        }
        if isinstance(result.get('_local_corroboration'),dict):
            facts['local_opportunity_corroboration']=result.get('_local_corroboration')
        local_label=str(local_review.get('remote_label') or 'Unknown')[:40]
        local_reason=str(local_review.get('remote_reason') or '')[:160]
        remote_text=(local_label+((' — '+local_reason) if local_reason else ''))[:220]
    if cloud_native:
        facts['cloud_research']={k:result.get(k) for k in ('country','engagement_type','company_size','founded_year','founded_by','salary','salary_estimate','role_feedback','role_info_provenance','role_info_confidence','application_process','application_process_role_specific','hiring_process_confidence','posted_date','age_days','current_status','recommendation','post_age_class','evergreen_confidence','evergreen_reason','confidence','sources','deep_verified','cloud_bundle_anchor','cloud_bundle_activities')}
        facts['cloud_research']['summary']=result.get('summary') or result.get('snippet','')
        role_bits=[]
        if result.get('salary'): role_bits.append('Advertised salary: '+str(result.get('salary')))
        if result.get('salary_estimate'): role_bits.append('Salary estimate: '+str(result.get('salary_estimate')))
        if result.get('role_feedback'): role_bits.append(str(result.get('role_feedback')))
        if role_bits:
            facts['role_info']={'summary':'\n'.join(role_bits)[:5000],'provenance':('Company/general' if 'company' in str(result.get('role_info_provenance') or '').lower() else 'Role-specific'),'confidence':str(result.get('role_info_confidence') or 'Medium').title(),'sources':list(result.get('sources') or [])[:8]}
        if str(result.get('application_process') or '').strip():
            facts['hiring_process']={'summary':str(result.get('application_process'))[:5000],'provenance':('Role-specific' if result.get('application_process_role_specific',True) else 'Company/general process'),'confidence':str(result.get('hiring_process_confidence') or 'Medium').title(),'sources':list(result.get('sources') or [])[:8]}
        if page_text:
            import hashlib as _hashlib
            facts['ai_job_summary']={'text':(result.get('summary') or result.get('snippet') or 'Cloud Web research verified this opportunity.')[:6000],'at':timezone.now().isoformat(),'source_hash':_hashlib.sha256(page_text.encode('utf-8','ignore')).hexdigest(),'source_text':page_text[:45000],'provider':result.get('cloud_provider',''),'model':result.get('cloud_model',''),'cloud_reused':True}
    if inspected.get('html'):
        facts['description_html']=inspected['html']
    company_intel={}
    if cloud_native and (company or result.get('company_size') or result.get('country')):
        ci_facts=[{'label':'Company','value':company}] if company else []
        for label,key in (('Location','country'),('Founded','founded_year'),('Founded by','founded_by'),('Size / structure','company_size'),('Engagement','engagement_type'),('Remote / eligibility','remote_text')):
            value=str(result.get(key) or '').strip()
            if value: ci_facts.append({'label':label,'value':value[:800],'verification':'verified' if result.get('sources') else 'estimate'})
        company_intel={'company':company,'confidence':int(result.get('confidence') or 60),'facts':ci_facts[:10],'structured':_cloud_company_structured(result),'sources':[{'provider':result.get('cloud_provider','Cloud AI'),'title':'Research source','url':u} for u in (result.get('sources') or [])[:12]],'errors':[],'status':'complete','updated_at':timezone.now().isoformat(),'cloud_reused':True}
    cloud_country=_company_country_value(result.get('country')) if cloud_native else ''
    age_days=result.get('age_days') if cloud_native else None
    fresh_label=''
    fresh_conf=0
    try:
        if age_days is not None:
            age_days=max(0,int(age_days)); fresh_label='Very fresh' if age_days<=3 else 'Fresh' if age_days<=14 else 'Possibly recent' if age_days<=45 else 'Uncertain / older' if age_days<=90 else 'Likely Old'; fresh_conf=max(40,min(95,int(result.get('confidence') or 65)))
    except Exception: pass
    local_status='new'
    local_reason='Discovery candidate verified against the target page; enrichment/ranking pending.'
    local_highlight=''
    if local_review:
        rec=str(local_review.get('recommendation') or '').strip().lower()
        local_status={'apply now':'apply','review':'review','information only':'info','reject':'rejected','unknown':'unknown'}.get(rec,'new')
        local_reason=str(local_review.get('fit_reason') or local_review.get('reason') or 'Local pre-persistence review verified this opportunity.')[:2000]
        local_highlight=str(local_review.get('highlight') or '').strip()[:600]
    blocked_row=is_blacklisted_url(target_url, scope='opportunities', company=company)
    if blocked_row:
        _reject('blacklisted_company' if not getattr(blocked_row,'domain','') else 'blacklisted_url')
        return None,False
    location_resolution=resolve_opportunity_location(
        target_url=target_url, inspected=inspected, page_title=page_title or title, page_text=page_text,
        direct_location_hint=result.get('_role_location_hint') or facts.get('direct_role_location_hint') or '',
        market_location_hint=result.get('_market_location_hint') or '',
        stored_role_location='', remote_text=remote_text, company_intel=company_intel, facts=facts,
    )
    facts['country_provenance']=location_resolution.get('provenance') or {}
    role_location=str(location_resolution.get('role_location') or '').strip()[:240]
    role_country=str(location_resolution.get('country') or '').strip()[:120]
    role_locations=normalize_location_items(location_resolution.get('locations') or role_country, source='role_location', evidence=role_location or role_country)

    # Second-stage duplicate identity runs only after final employer/location/content are
    # known. This is what lets Jobicy, ATS and direct-employer representations collapse
    # into one primary vacancy without merging genuinely separate requisitions/locations.
    family_dup=active_role_family_duplicate(
        title,company,target_url,page_text,role_location=role_location,country=role_country,
        days=max(90,int(cfg.duplicate_window_days or 90)),
    )
    if family_dup:
        return _merge_secondary_opportunity_duplicate(
            family_dup,campaign=campaign,source=source,query=query,target_url=target_url,search_url=search_url,
            title=title,company=company,page_text=page_text,provenance=provenance,facts=facts,result=result,
            role_location=role_location,role_country=role_country,lead_collector=lead_collector,
            reason='same employer vacancy/role family found through another source',
        )

    concentration=company_concentration_decision(
        company,target_url,title,page_text,pre_score,role_location=role_location,country=role_country,
        days=14,base_fit_threshold=int(opportunity_thresholds(selectivity_current('opportunities')).get('fit_score') or 0),
    )
    facts['company_concentration_evaluation']={k:v for k,v in concentration.items() if k!='anchor'}
    if not concentration.get('allow') and concentration.get('anchor'):
        return _store_company_concentration_overflow(
            concentration['anchor'],campaign=campaign,source=source,query=query,target_url=target_url,title=title,
            company=company,page_text=page_text,pre_score=pre_score,role_location=role_location,role_country=role_country,
            provenance=provenance,decision=concentration,lead_collector=lead_collector,
        )

    opp=Opportunity.objects.create(
        title=title,company=company,country=role_country,locations=role_locations,role_location=role_location,url=target_url,search_url=search_url,target_url=target_url,canonical_url=can,source=source,remote_text=remote_text,language_code=language,
        channel=infer_channel(target_url,title,page_text,result,source),description=page_text[:45000],raw_search_snippet=search_snippet,
        contact_email=_best_discovery_contact_email(result,page_text,search_snippet,company,target_url,cloud_native=cloud_native),
        note=(_distinctive_cloud_note(result) if cloud_native else ''),
        list_highlight=(opportunity_specific_highlight(result=(result if cloud_native else local_review or result),title=title,description=page_text or search_snippet,facts=facts,remote_text=remote_text)[:600]),
        fit_score=pre_score,status=(_cloud_recommendation_status(result) if result.get('cloud_discovery') else local_status),recommendation_reason=(str(result.get('fit_reason') or '').strip()[:2000] if cloud_native else local_reason),
        extracted_facts=facts, company_intel=company_intel, freshness_label=fresh_label, freshness_confidence=fresh_conf, data_downloaded_bytes=int(inspected.get('bytes') or 0),
        target_http_status=(int(inspected.get('http_status')) if inspected.get('http_status') is not None else None),
        target_checked_at=(timezone.now() if inspected.get('http_status') is not None or inspected.get('error') else None),
        target_check_error=str(inspected.get('error') or '')[:500],
    )
    if opp.channel == 'email' and not opp.contact_email:
        opp.channel = 'website'
        opp.save(update_fields=['channel'])
    # Cloud Web already asked the provider for compensation as part of candidate research.
    # Local GPU mode never calls Cloud AI for salary: it performs only a quick regex parse
    # of the retained JD/page text, so missing salary can never stall or crash a local run.
    try:
        salary_info=(salary_from_retained_opportunity(opp) or salary_from_cloud_result(result,target_url)) if cloud_native else salary_from_retained_opportunity(opp)
        if not salary_info and result.get('_title_salary_evidence'):
            parsed=parse_salary_text(str(result.get('_title_salary_evidence') or ''))
            if parsed:
                salary_info={
                    'salary_text':parsed.get('text') or result.get('_title_salary_evidence'),'salary_currency':parsed.get('currency') or '',
                    'salary_min':parsed.get('min'),'salary_max':parsed.get('max'),'salary_period':parsed.get('period') or '',
                    'salary_source_type':'post','salary_source_url':target_url,'salary_confidence':88,'salary_checked_at':timezone.now(),
                }
        if salary_info: apply_salary_info(opp,salary_info,save=True)
    except Exception:
        # Compensation is optional enrichment. Discovery must continue even if a malformed
        # salary string or unexpected legacy row cannot be parsed.
        pass
    attribute_campaign(opp,campaign)
    if result.get('published_at'):
        OpportunityEvidence.objects.create(opportunity=opp,kind='search_or_source_date',label=('Forum post date' if is_forum_result else ('Direct source publication date' if result.get('_publication_authoritative') else 'Source/search publication date')),value=result['published_at'],source_url=target_url,confidence=(96 if result.get('_publication_authoritative') else 85),metadata={'authoritative_source_timestamp':bool(result.get('_publication_authoritative')),'forum_post_timestamp':bool(is_forum_result),'used_for_post_age':bool(is_forum_result)})
    enrichment_result={}
    try: enrichment_result=enrich(opp,allow_ai=(not cloud_native and not bool(local_review))) or {}
    except Exception as e:
        opp.recommendation_reason=(opp.recommendation_reason+' Enrichment incomplete: '+str(e))[:2000]; opp.save(update_fields=['recommendation_reason','updated_at'])
    # Remote is a persistence requirement for the whole product, not merely a score.
    # Cloud rows were grounded before ingestion; Local AI Discovery rows are settled by the
    # configured Fit/Remote classifier. Unknown, hybrid and on-site items stay out.
    remote_gate=(opp.extracted_facts or {}).get('remote_classification') or {}
    remote_status=str(remote_gate.get('status') or 'unknown').strip().lower()
    try: remote_conf=int(remote_gate.get('confidence') or 0)
    except Exception: remote_conf=0
    if remote_status not in {'fully_remote','remote'} or remote_conf < 55:
        UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else '',stage='remote_requirement_review',requests=1,pages=1,metadata={'url':target_url,'remote_status':remote_status,'remote_confidence':remote_conf})
        # ScoutBox is a remote-opportunity finder: unknown is not affirmative evidence.
        # Retain the row for audit/recovery but keep it out of the active Opportunity list.
        opp.status='rejected'; opp.suppressed=True
        if remote_status in {'hybrid','onsite'}:
            reason=f'Non-remote working arrangement: {remote_status} ({remote_conf}%).'
        else:
            reason='Remote work eligibility could not be confirmed from role-level evidence.'
        opp.rejection_reason=reason[:2000]
        opp.save(update_fields=['status','suppressed','rejection_reason','updated_at'])
        _reject('remote_ineligible')
        return None,False
    try:
        promote_record_contact_to_addressbook(
            opp,source=('Cloud Web Opportunity' if cloud_native else 'Source-guided Opportunity'),source_url=target_url,
            texts=(page_text,page_title,search_snippet),confidence=(88 if cloud_native else 78),queue_research=False,
        )
    except Exception:
        pass
    # A concrete Opportunity owns this company/domain in review surfaces. Any generic
    # Hidden Lead for the same organization is moved out of the active list.
    try:
        suppress_overlapping_leads(opp)
    except Exception:
        pass
    # Cloud Web freshness is already resolved by a grounded Cloud verification pass.
    # Reuse that evidence so a hard Cloud run can never leak into local/Ollama freshness.
    # Local AI Discovery opportunities continue to use cleaned page content + cautious HTTP evidence.
    try:
        if cloud_native: apply_cloud_post_age(opp,result)
        else: recompute(opp)
    except Exception: pass
    # Initial passive enrichment is one-shot per evidence generation. Cloud-native
    # discovery reuses its grounded summary/company research and therefore avoids the
    # redundant follow-up calls entirely.
    if not cloud_native:
        try:
            from celery import current_app
            cfg=PortalSettings.objects.get_or_create(pk=1)[0]
            source_text=(opp.description or opp.raw_search_snippet or '').strip()
            if cfg.feature_page_summarization and route_for_stage('page_summarization') and source_text:
                allowed,_=reserve_attempt(opp,'summary','initial')
                if allowed:
                    job=BackgroundJob.objects.create(kind='summarize',label=f'Summarize: {opp.title}'[:300],message='Queued',result={'opportunity_id':opp.pk,'ai_kind':'summary','ai_phase':'initial'})
                    async_result=current_app.send_task('portal.tasks.opportunity_summary_job',args=[job.pk,opp.pk,'initial'])
                    job.celery_task_id=getattr(async_result,'id','') or ''; job.save(update_fields=['celery_task_id'])
            if opp.company and route_for_stage('company_enrichment'):
                allowed,_=reserve_attempt(opp,'company','initial')
                if allowed:
                    cjob=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {opp.company or opp.title}'[:300],message='Queued',result={'opportunity_id':opp.pk,'ai_kind':'company','ai_phase':'initial'})
                    async_result=current_app.send_task('portal.tasks.company_research_job',args=[cjob.pk,opp.pk,'initial'])
                    cjob.celery_task_id=getattr(async_result,'id','') or ''; cjob.save(update_fields=['celery_task_id'])
        except Exception:
            pass
    st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate())
    if (enrichment_result.get('application_history') or {}).get('exact_role'):
        st.applied_matches+=1; st.save(update_fields=['applied_matches'])
        return opp,False
    st.unique_results+=1; st.save(update_fields=['unique_results'])
    return opp,True



def _cloud_qualify_direct_records(campaign, records, *, cap, progress_callback=None, should_stop=None, progress_start=42, progress_span=6, label='fresh source'):
    """Qualify a small direct/forum batch through the configured Cloud route.

    The helper deliberately runs after provider-native Cloud discovery in a normal Cloud
    campaign. Forum-only passes also reuse it, but those passes are scheduled on the
    low-priority forum queue and cooperatively yield whenever primary discovery appears.
    """
    verified=[]
    qualification_records=list(records or [])[:max(0,int(cap or 0))]
    for idx,rec in enumerate(qualification_records,1):
        _check_stop(should_stop)
        _progress(progress_callback,progress_start+int(progress_span*idx/max(1,len(qualification_records))),f'Qualifying {label} {idx}/{len(qualification_records)}')
        candidate=dict(rec.get('result') or {})
        if candidate.get('_community_hiring_signal'):
            # Community/forum items are not forced through vacancy semantics in Cloud Web.
            # Verify the employer/hiring signal with the configured Cloud route and persist
            # it later as a Hidden Lead. The discussion URL remains evidence, not employer.
            signal_review=research_hiring_signal(campaign,candidate,page_text=str(candidate.get('snippet') or ''))
            if not signal_review:
                continue
            researched=dict(candidate)
            researched['_cloud_community_signal']=True
            researched['_cloud_community_signal_review']=signal_review
            evidence=' '.join(x for x in (str(candidate.get('snippet') or '').strip(),str(signal_review.get('evidence') or '').strip()) if x)
            researched['_page_text']=evidence[:45000]
            researched['_page_ok']=True
            researched['_source_content_direct']=bool(candidate.get('_direct_source'))
            researched['_provenance']=(candidate.get('_provenance') or []) + [{
                'source':'Cloud AI hiring-signal verification','query':'Community hiring-signal qualification',
                'url':candidate.get('url',''),'cloud_provider':signal_review.get('cloud_provider',''),
                'cloud_model':signal_review.get('cloud_model',''),
            }]
            verified.append({'result':researched,'source':rec.get('source'),'query':rec.get('query') or 'Community Hiring Signal'})
            continue
        researched=research_candidate(campaign,candidate,page_text=str(candidate.get('snippet') or ''))
        if not researched:
            continue
        direct_opp_level=selectivity_current('opportunities'); direct_opp_policy=opportunity_thresholds(direct_opp_level)
        if direct_opp_level=='specialist':
            direct_ok=int(researched.get('confidence') or 0)>=int(direct_opp_policy['confidence']) and int(researched.get('_pre_score') or researched.get('fit_score') or 0)>=int(direct_opp_policy['fit_score'])
            if direct_ok:
                direct_ok,direct_hits=specialist_alignment(campaign,researched.get('title') or candidate.get('title') or '', ' '.join(str(researched.get(k) or '') for k in ('summary','highlight','evidence','fit_reason'))+' '+str(candidate.get('snippet') or ''),kind='opportunity')
            else:
                direct_hits=[]
            if not direct_ok:
                UsageMetric.objects.create(category='discovery_filter',provider='cloud_web',stage='specialist_opportunity_selectivity',requests=1,pages=1,metadata={'url':researched.get('url') or candidate.get('url'),'title':researched.get('title') or candidate.get('title'),'selectivity':direct_opp_level,'specialist_hits':direct_hits})
                continue
            researched['_opportunity_selectivity']={'level':direct_opp_level,'specialist_hits':direct_hits}
        researched['_direct_source']=True
        researched['_direct_adapter']=candidate.get('_direct_adapter','')
        researched['_direct_item_id']=candidate.get('_direct_item_id','')
        researched['_acquisition_path']=candidate.get('_acquisition_path','Direct source')
        for field in ('_forum_source','_forum_name','_forum_base_url','_forum_software','_forum_search_path','_forum_post_date','_forum_post_id','_forum_query','_source_category_override','_apply_via','_role_location_hint','_market_location_hint','_community_hiring_signal','_community_kind','_structured_signal_evidence','_news_signal','_signal_only','_searchapi_source_name','_searchapi_source_domain'):
            if candidate.get(field):
                researched[field]=candidate.get(field)
        if candidate.get('_forum_source'):
            researched['_source_category_override']='forum'
            researched['_apply_via']='forum'
        researched['published_at']=candidate.get('published_at') or researched.get('posted_date') or ''
        researched['_publication_authoritative']=bool(candidate.get('_publication_authoritative'))
        if str(candidate.get('snippet') or '').strip():
            researched['_page_text']=str(candidate.get('snippet') or '')[:45000]
            researched['_page_ok']=True
            researched['_source_content_direct']=True
        if candidate.get('_publication_authoritative') and candidate.get('published_at'):
            researched['posted_date']=candidate.get('published_at')
            researched['posted_date_explicit']=True
            researched['post_age_method']='explicit'
            researched['post_age_reason']='Specific forum post timestamp; thread bumps are ignored.' if candidate.get('_forum_source') else 'Direct source publication timestamp.'
        researched['_provenance']=(candidate.get('_provenance') or []) + [{
            'source':'Cloud AI verification','query':('Forum candidate qualification' if candidate.get('_forum_source') else 'Fresh Source candidate qualification'),'url':researched.get('url',''),
            'cloud_provider':researched.get('cloud_provider',''),'cloud_model':researched.get('cloud_model',''),
        }]
        for key in ('_community_thread_url','_community_thread_title','_ats_board','_reddit_subreddit','_reddit_author'):
            if candidate.get(key):
                researched[key]=candidate.get(key)
        verified.append({'result':researched,'source':rec.get('source'),'query':rec.get('query') or ('Forum Discovery' if candidate.get('_forum_source') else 'Fresh Source Discovery')})
    return verified


def _run_cloud_native_campaign(campaign, cfg, test=False, progress_callback=None, should_stop=None):
    _progress(progress_callback,8,'Preparing context'); _check_stop(should_stop)
    # Provider-native Cloud research is the primary work and always runs first. Direct
    # adapters are bounded supplementary acquisition. Forum adapters are intentionally
    # absent here: they run independently on the idle-only forum queue so they cannot
    # delay or consume a primary Cloud campaign worker slot.
    direct_search_profile=build_search_profile(campaign)
    _progress(progress_callback,12,'Cloud research')
    cloud=cloud_discover(campaign,max_results=(cfg.cloud_test_candidates if test else cfg.cloud_discovery_candidates_per_run),test=test)
    _check_stop(should_stop)

    try:
        direct_stage_budget=max(20,min(300,int(os.environ.get('SCOUTBOX_DIRECT_SOURCE_STAGE_MAX_SECONDS','60') or 60)))
    except Exception:
        direct_stage_budget=60
    direct_limit=(10 if test else min(60,int(cfg.cloud_discovery_candidates_per_run or 50)))
    direct_source_cap=3 if test else max(3,min(10,int(os.environ.get('SCOUTBOX_DIRECT_SOURCE_MAX_SOURCES','6') or 6)))
    _progress(progress_callback,38,'Checking fresh direct sources')
    direct_records,direct_errors,direct_meta=non_forum_direct_source_rows(
        campaign,direct_search_profile,limit=direct_limit,test=test,progress_callback=progress_callback,should_stop=should_stop,
        stage_budget_seconds=direct_stage_budget,max_sources=direct_source_cap,
    )
    direct_cap=3 if test else max(3,min(6,int(cfg.cloud_discovery_candidates_per_run or 50)//6))
    verified_direct=_cloud_qualify_direct_records(
        campaign,direct_records,cap=direct_cap,progress_callback=progress_callback,should_stop=should_stop,
        progress_start=40,progress_span=8,label='fresh source',
    )

    source=cloud['source']; raw_records=[]
    for result in cloud.get('results',[]):
        result['_provenance']=[{
            'source':source.name,'query':'Cloud Web Discovery','url':result.get('url',''),
            'cloud_provider':cloud.get('provider',''),'cloud_model':cloud.get('model',''),
            'evidence_urls':result.get('sources') or [],
        }]
        raw_records.append({'result':result,'source':source,'query':'Cloud Web Discovery'})
    raw_records.extend(verified_direct)
    _check_stop(should_stop); _progress(progress_callback,50,'Inspecting candidates')
    _progress(progress_callback,55,'Verifying URLs')
    consolidated=consolidate_cloud_results(raw_records)
    unique=0; opportunity_ids=[]; lead_collector={'ids':[],'new':0,'duplicates':0}; filter_collector={}; total=max(1,len(consolidated))
    for idx,item in enumerate(consolidated,1):
        _check_stop(should_stop); _progress(progress_callback,58+int(24*idx/total),f'Qualifying leads · {idx}/{total}')
        primary=item.pop('_source_obj')
        opp,isnew=ingest_result(item,primary,campaign,'Cloud Web Discovery',lead_collector=lead_collector,filter_collector=filter_collector); unique+=int(isnew)
        if opp and item.get('_discovery_market_code'):
            UsageMetric.objects.create(category='discovery_market',provider=primary.name if primary else 'Cloud Web',stage='retained',pages=1,metadata={'market_code':item.get('_discovery_market_code'),'market':item.get('_discovery_market',''),'multilingual_language':item.get('_multilingual_language',''),'opportunity_id':opp.pk})
        if opp and opp.pk not in opportunity_ids: opportunity_ids.append(opp.pk)
    # Cloud-returned URLs are also useful for contacts and hidden-market discovery.
    _progress(progress_callback,86,'Validating contacts')
    contacts_created=persist_cloud_contacts(cloud.get('contact_rows') or [],source_name=('Cloud Web · '+source.name if source else 'Cloud Web'))
    cloud_leads=persist_cloud_hidden_leads(campaign,source,cloud.get('hidden_leads') or [])
    for lead_id in cloud_leads.get('ids',[]):
        if lead_id not in lead_collector['ids']: lead_collector['ids'].append(lead_id)
    lead_collector['new']=int(lead_collector.get('new') or 0)+int(cloud_leads.get('created') or 0)
    _progress(progress_callback,94,'Persisting results')
    campaign.last_run=timezone.now(); campaign.save(update_fields=['last_run'])
    forum_meta={'executed':False,'isolated':True,'reason':'Forum discovery is scheduled independently on the forum queue only when primary discovery is idle.'}
    return {
        'discovery_mode':'cloud_web','providers':[cloud.get('provider','')],'models':[cloud.get('model','')],
        'execution_provider':cloud.get('provider',''),'execution_model':cloud.get('model',''),
        'execution_path':('Cloud Web · '+str(cloud.get('provider') or 'Cloud AI').title()+' · '+str(cloud.get('model') or 'auto')),
        'queries':cloud.get('queries',[]),'cv_count':cloud.get('search_profile',{}).get('cv_count',0),
        'top_profile_terms':[x['term'] for x in cloud.get('search_profile',{}).get('skills',[])[:12]],
        'raw_hits':len(raw_records),'consolidated_hits':len(consolidated),
        'duplicates_merged_before_enrichment':max(0,len(raw_records)-len(consolidated)),
        'duplicates':max(0,len(raw_records)-len(consolidated))+int(lead_collector.get('duplicates') or 0),
        'unique':unique,'new_opportunities':unique,'opportunities_found':unique,'rediscovered_opportunities':max(0,len(opportunity_ids)-unique),'opportunity_ids':opportunity_ids,
        'leads_found':lead_collector['new'],'new_leads':lead_collector['new'],'rediscovered_leads':max(0,len(lead_collector['ids'])-int(lead_collector['new'] or 0)),'lead_ids':lead_collector['ids'],'errors':list(direct_errors),'error_count':len(direct_errors),
        'location_policy':'Location is supplied as an eligibility/fit constraint to cloud research, not multiplied into keyword searches.',
        'cloud_native':True,'deep_researched':cloud.get('deep_researched',0),
        'cloud_urls_returned':cloud.get('urls_returned',0),'cloud_urls_inspected':cloud.get('urls_inspected',0),
        'cloud_resolver_retries':cloud.get('resolver_retries',0),'contacts_created':contacts_created,
        'cloud_verified_candidates':int(cloud.get('verified_candidates') or 0),
        'cloud_unresolved_after_retries':int(cloud.get('unresolved_after_retries') or 0),
        'cloud_final_urls_inspected':cloud.get('final_urls_inspected',0),
        'cloud_hidden_lead_candidates':cloud.get('hidden_lead_candidates',0),
        'cloud_hidden_leads_qualified':cloud.get('hidden_leads_qualified',0),
        'cloud_hidden_leads_rejected':cloud.get('hidden_leads_rejected',0),
        'cloud_contact_candidates':cloud.get('contact_candidates',0),
        'cloud_contacts_validated':cloud.get('contacts_validated',0),
        'cloud_contacts_rejected':cloud.get('contacts_rejected',0),
        'cloud_hidden_leads_created':int(cloud_leads.get('created') or 0),
        'cloud_persistence_rejections':filter_collector,
        'selected_cv_ids':cloud.get('search_profile',{}).get('selected_cv_ids',[]),
        'fresh_source_discovery':{**(direct_meta or {}),'cloud_qualified':len(verified_direct)},
        'forum_discovery':forum_meta,
        'search_engine_discovery':{'executed':False,'reason':'Cloud Web uses provider-native Cloud Web discovery plus a bounded post-pass of direct adapters; ScoutBox search engines are bypassed.'},
        'fresh_source_errors':direct_errors,
        'market_coverage':cloud.get('market_coverage') or {},
        'multilingual_exploration':cloud.get('multilingual_exploration') or {},
    }

def _company_career_page_records(campaign, providers, search_profile, cfg, *, test=False, progress_callback=None, should_stop=None):
    """Local-only two-stage company-career discovery.

    Stage one uses ordinary configured search engines to locate plausible employer domains.
    Stage two searches only those domains for current hiring/collaboration/project pages and
    returns item-level candidates to the normal Local AI ingestion pipeline.  The umbrella
    SearchSource is deliberately not a direct adapter and is never invoked by Cloud Web.
    """
    umbrella=SearchSource.objects.filter(name='Company career pages',enabled=True).first()
    if not umbrella or not providers:
        return [],[],{'enabled':bool(umbrella),'requests':0,'company_domains':[],'candidates':0}
    skills=[str(x.get('term') or '').strip() for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    roles=[str(x.get('role') or '').strip() for x in (search_profile.get('role_families') or []) if str(x.get('role') or '').strip()]
    locations=[str(x).strip() for x in (getattr(campaign,'locations',None) or []) if str(x).strip()]
    location=(locations[0] if locations else str(getattr(campaign,'location','') or '').strip())[:100]
    target_market=market_from_location(location)
    providers=[provider for provider in providers if provider.name!='SearchAPI · Google Jobs' and provider_market_compatible(provider,target_market)]
    if not providers:
        return [],[],{'enabled':True,'requests':0,'company_domains':[],'candidates':0,'market':getattr(target_market,'code','')}

    # Company-finding searches must stay human-sized.  Older builds joined two full role
    # titles with several generic hiring phrases, which produced noisy requests such as
    # ``emulation engineer legacy systems specialist Singapore hiring company careers``.
    # Use one rotating role alias, at most one concise technical term, the market/location,
    # and one hiring intent.  This both shortens provider queries and prevents the same
    # literal job title (for example ``legacy systems specialist``) from dominating every run.
    role_variants=[]
    for role in roles[:6]:
        for alias in [role]+_role_alias_fallback(role):
            alias=' '.join(str(alias or '').split())
            if not alias or len(alias.split())>4:
                continue
            if alias.casefold() not in {x.casefold() for x in role_variants}:
                role_variants.append(alias)
    if not role_variants:
        role_variants=['software engineer']

    technical_terms=[]
    role_word_sets=[set(re.findall(r'[a-z0-9+#.-]+',x.casefold())) for x in role_variants]
    for skill in skills[:40]:
        term=' '.join(str(skill or '').split())
        words=re.findall(r'[A-Za-z0-9+#./-]+',term)
        if not words or len(words)>3:
            continue
        low=set(w.casefold() for w in words)
        if any(low and low.issubset(role_words) for role_words in role_word_sets):
            continue
        if term.casefold() not in {x.casefold() for x in technical_terms}:
            technical_terms.append(term)
    if not technical_terms:
        technical_terms=['technical']

    rotation_bucket=int(time.time()//(2*60*60))+int(getattr(campaign,'pk',0) or 0)
    hiring_intents=['hiring','careers','jobs','vacancies']

    def compact_company_query(offset=0, *, domain=''):
        role=role_variants[(rotation_bucket+offset)%len(role_variants)]
        tech=technical_terms[(rotation_bucket*3+offset)%len(technical_terms)] if technical_terms else ''
        intent=hiring_intents[(rotation_bucket+offset)%len(hiring_intents)]
        parts=[]
        if domain:
            parts.append(f'site:{domain}')
        parts.append(f'"{role}"')
        if tech and tech.casefold() not in role.casefold():
            parts.append(f'"{tech}"' if ' ' in tech else tech)
        if location and not domain:
            parts.append(location)
        parts.append(intent)
        return ' '.join(parts).strip()
    records=[]; errors=[]; domains=[]; requests=0
    skip_hosts={'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','monster.com','dice.com','careerbuilder.com','wellfound.com','builtin.com','remoteok.com','weworkremotely.com','remotive.com','himalayas.app','jobicy.com','github.com','reddit.com','ycombinator.com'}
    provider_cap=1 if test else min(2,len(providers))
    for pidx,provider in enumerate(providers[:provider_cap],1):
        _check_stop(should_stop)
        progress=43+min(3,pidx)
        seed_query=compact_company_query(pidx-1)
        found,err=_search_source_with_liveness(provider,seed_query,5 if test else 8,progress_callback,progress,'Locating companies with relevant hiring signals',should_stop,market=target_market); requests+=1
        if err: errors.append(f'{provider.name}/company discovery: {err}'); continue
        for row in found or []:
            url=str(row.get('url') or '').strip()
            try: host=(urllib.parse.urlsplit(url).hostname or '').lower().lstrip('www.')
            except Exception: host=''
            domain=registrable_domain(host) if host else ''
            if not domain or domain in skip_hosts or any(domain==x or domain.endswith('.'+x) for x in skip_hosts): continue
            if is_general_market_host(url) or is_blacklisted_url(url,scope='all'): continue
            if domain not in domains: domains.append(domain)
            if len(domains)>=(3 if test else 10): break
        if len(domains)>=(3 if test else 10): break
    # A provider that failed the seed request is not retried for every discovered domain.
    # This supplementary stage must remain bounded even when a public endpoint times out.
    providers=[provider for provider in providers[:provider_cap] if provider.name not in {error.split('/',1)[0] for error in errors}]
    if not providers:
        return records,errors,{'enabled':True,'requests':requests,'company_domains':domains,'candidates':0,'market':getattr(target_market,'code','')}
    provider_cap=len(providers)
    for idx,domain in enumerate(domains,1):
        _check_stop(should_stop)
        provider=providers[(idx-1)%provider_cap]
        q=compact_company_query(idx,domain=domain)
        progress=45+int(3*idx/max(1,len(domains)))
        found,err=_search_source_with_liveness(provider,q,4 if test else 7,progress_callback,progress,f'Checking company opportunities: {domain}',should_stop,market=target_market); requests+=1
        if err:
            errors.append(f'{provider.name}/{domain}: {err}')
            providers=[candidate for candidate in providers if candidate.pk!=provider.pk]
            if not providers: break
            provider_cap=len(providers)
            continue
        for row in found or []:
            item=dict(row or {})
            url=str(item.get('url') or '').strip()
            try: item_host=(urllib.parse.urlsplit(url).hostname or '').lower().lstrip('www.')
            except Exception: item_host=''
            if not item_host or registrable_domain(item_host)!=domain: continue
            # A search-engine title is only a pointer. Fetch the employer page directly and
            # require item-level role evidence plus CV/profile relevance before returning it.
            fetched=_direct_fetch(url,str(item.get('title') or ''),str(item.get('snippet') or ''),purpose='company_career_direct_search')
            if not fetched.get('ok') or int(fetched.get('http_status') or 0) in (404,410):
                continue
            final=str(fetched.get('target_url') or url).strip()
            ftitle=sanitize_mixed_script_title(str(fetched.get('title') or item.get('title') or ''))
            ftext=str(fetched.get('text') or '')
            gate=classify_role_page(final,ftitle,ftext,has_jobposting_schema=bool(fetched.get('has_jobposting_schema')),is_pdf=bool(fetched.get('is_pdf')))
            if not gate.get('accepted') or soft_missing_reason(ftitle,ftext):
                continue
            if search_profile:
                grounded=grounded_profile_relevance(ftitle,ftext,search_profile,strict_market=True)
                if not grounded.get('accepted'):
                    continue
                item['_matched_profile_terms']=grounded.get('matches') or []
                item['_grounded_profile_relevance']=grounded
            item['url']=final; item['title']=ftitle or item.get('title'); item['snippet']=ftext[:12000]
            item['_company_career_discovery']=True
            item['_acquisition_path']='Company career pages · direct verified'
            item['_provenance']=[{'source':'Company career pages','query':q,'url':final,'acquisition_path':'Local search-engine discovery + direct employer-page validation','company_domain':domain}]
            records.append({'result':item,'source':provider,'query':q})
    UsageMetric.objects.create(category='company_career_discovery',provider='Local search engines',stage='company_career_pages',requests=requests,pages=0,metadata={'company_domains':domains[:20],'candidates':len(records),'direct_verified':len(records),'umbrella_source_id':umbrella.pk})
    return records,errors,{'enabled':True,'requests':requests,'company_domains':domains,'candidates':len(records)}



def _run_forum_only_campaign(campaign, cfg, test=False, progress_callback=None, should_stop=None, discovery_mode='source_guided'):
    """Run a low-priority, bounded Forum-only discovery pass.

    Forum acquisition never runs inline with a primary Local/Cloud campaign. Automatic
    passes use their own Celery queue and are launched only during primary-discovery idle
    time. The worker also checks ``should_stop`` between bounded operations so a newly
    queued primary campaign can reclaim capacity quickly.
    """
    mode=str(discovery_mode or 'source_guided').strip().lower()
    if mode not in {'source_guided','cloud_web'}:
        mode='source_guided'
    _check_stop(should_stop); _progress(progress_callback,8,'Preparing forum context')
    search_profile=build_search_profile(campaign)
    forum_limit=(8 if test else min(36,max(16,int(getattr(cfg,'max_results_per_query',100) or 100)//3)))
    try:
        forum_stage_budget=max(10,min(25,int(os.environ.get('SCOUTBOX_FORUM_ONLY_STAGE_MAX_SECONDS','25') or 25)))
    except Exception:
        forum_stage_budget=25
    try:
        forum_source_cap=max(1,min(3,int(os.environ.get('SCOUTBOX_FORUM_FAILOVER_SOURCES_PER_PASS','3') or 3)))
    except Exception:
        forum_source_cap=3
    _progress(progress_callback,10,'Browsing forum sources')
    forum_records,forum_errors,forum_meta=forum_source_rows(
        campaign,search_profile,limit=forum_limit,test=test,progress_callback=progress_callback,
        should_stop=should_stop,stage_budget_seconds=forum_stage_budget,max_sources=forum_source_cap,
    )
    raw_records=list(forum_records or [])
    errors=list(forum_errors or [])
    # In Source Guided mode SearchAPI Google Forums is an independent fallback/discovery
    # lane for Reddit, Stack Exchange, vendor forums and niche communities. This is useful
    # when a native Reddit endpoint is blocked or unhealthy. Cloud Web mode intentionally
    # does not call a local/SERP provider and instead qualifies native community adapters.
    forum_signal_meta={}
    if mode=='source_guided':
        rotation_offset=timezone.localdate().toordinal()+int(getattr(campaign,'pk',0) or 0)
        coverage=market_plan(cfg,campaign_id=getattr(campaign,'pk',0),rotation_offset=rotation_offset)
        signal_rows,signal_errors,forum_signal_meta=_searchapi_signal_records(
            campaign,cfg,search_profile,coverage.get('markets') or [],test=test,
            progress_callback=progress_callback,should_stop=should_stop,rotation_offset=rotation_offset,
            include_news=False,forum_only=True,
        )
        raw_records.extend(signal_rows or [])
        errors.extend(signal_errors or [])
        forum_meta={**(forum_meta or {}),'searchapi_forums':forum_signal_meta}
    if not raw_records:
        return {
            'discovery_mode':mode,'forum_only':True,'primary_throughput_isolated':True,
            'execution_path':('Cloud Web · Forum idle pass' if mode=='cloud_web' else 'Local AI Discovery · Forum idle pass'),
            'providers':['Forum'],'queries':[],
            'cv_count':search_profile.get('cv_count',0),
            'top_profile_terms':[x['term'] for x in search_profile.get('skills',[])[:12] if isinstance(x,dict) and x.get('term')],
            'raw_hits':0,'consolidated_hits':0,'duplicates':0,'unique':0,
            'new_opportunities':0,'opportunities_found':0,'opportunity_ids':[],
            'leads_found':0,'new_leads':0,'lead_ids':[],
            'errors':errors,'error_count':len(errors),'forum_discovery':forum_meta,
            'followup_discovery':{'pages_checked':0,'page_limit':0,'depth_limit':0,'queued_remaining':0},
        }

    _check_stop(should_stop); _progress(progress_callback,36,'Consolidating forum candidates')
    expanded=[]
    for rec in raw_records:
        expanded.extend(_expand_aggregate_record(rec))
    raw_records=expanded
    unique=0; opportunity_ids=[]; lead_collector={'ids':[],'new':0,'duplicates':0}; filter_collector={}

    if mode=='cloud_web':
        try:
            cloud_cap=max(1,min(5,int(os.environ.get('SCOUTBOX_FORUM_CLOUD_QUALIFICATION_MAX','1') or 2)))
        except Exception:
            cloud_cap=1
        verified=_cloud_qualify_direct_records(
            campaign,raw_records,cap=(2 if test else cloud_cap),progress_callback=progress_callback,
            should_stop=should_stop,progress_start=40,progress_span=30,label='forum candidate',
        )
        consolidated=consolidate_cloud_results(verified)
        total=max(1,len(consolidated))
        for idx,item in enumerate(consolidated,1):
            _check_stop(should_stop)
            _progress(progress_callback,72+int(20*idx/total),f'Persisting forum candidate {idx}/{total}')
            primary=item.pop('_source_obj')
            opp,isnew=ingest_result(item,primary,campaign,'Forum idle pass · Cloud qualification',lead_collector=lead_collector,filter_collector=filter_collector)
            unique+=int(isnew)
            if opp and opp.pk not in opportunity_ids:
                opportunity_ids.append(opp.pk)
        followup_processed=0; followup_limit=0; followup_depth=0; queued_remaining=0
    else:
        consolidated=consolidate_results(raw_records,search_profile)
        try:
            local_cap=max(1,min(12,int(os.environ.get('SCOUTBOX_FORUM_LOCAL_QUALIFICATION_MAX','1') or 2)))
        except Exception:
            local_cap=1
        consolidated=consolidated[:(3 if test else local_cap)]
        try:
            followup_limit=max(0,min(12,int(os.environ.get('SCOUTBOX_FORUM_FOLLOWUP_PAGES','0') or 1)))
        except Exception:
            followup_limit=0
        followup_depth=max(0,min(2,int(getattr(cfg,'followup_link_depth',2) or 0)))
        followups={'queue':[],'seen':set(),'max_depth':followup_depth}
        for rec in raw_records:
            try:
                u=canonical(str((rec.get('result') or {}).get('url') or ''))
                if u: followups['seen'].add(u)
            except Exception:
                pass
        total=max(1,len(consolidated))
        for idx,item in enumerate(consolidated,1):
            _check_stop(should_stop)
            _progress(progress_callback,42+int(40*idx/total),f'Analysing forum candidate {idx}/{total}')
            primary=item.pop('_source_obj')
            primary_query=(item.get('_provenance') or [{}])[0].get('query','Forum browsing')
            opp,isnew=ingest_result(
                item,primary,campaign,primary_query,lead_collector=lead_collector,search_profile=search_profile,
                followup_collector=followups if followup_limit and followup_depth else None,followup_depth=0,
            )
            unique+=int(isnew)
            if opp and opp.pk not in opportunity_ids:
                opportunity_ids.append(opp.pk)
        followup_processed=0
        while followup_limit and followup_depth and followups['queue'] and followup_processed<followup_limit:
            _check_stop(should_stop)
            rec=followups['queue'].pop(0); depth=int(rec.get('depth') or 1)
            if depth>followup_depth:
                continue
            followup_processed+=1
            _progress(progress_callback,84+int(12*followup_processed/max(1,followup_limit)),f'Checking forum follow-up {followup_processed}/{followup_limit} · depth {depth}/{followup_depth}')
            item=dict(rec.get('result') or {}); primary=rec.get('source'); q=rec.get('query') or 'Forum follow-up link'
            try:
                opp,isnew=ingest_result(item,primary,campaign,q,lead_collector=lead_collector,search_profile=search_profile,followup_collector=followups,followup_depth=depth)
                unique+=int(isnew)
                if opp and opp.pk not in opportunity_ids:
                    opportunity_ids.append(opp.pk)
            except Exception as exc:
                errors.append(f'Forum follow-up {item.get("url","")[:180]}: {exc}')
        queued_remaining=len(followups['queue'])
        if followup_processed:
            UsageMetric.objects.create(category='followup_discovery',provider='Forum',stage='bounded_forum_followup',requests=followup_processed,pages=followup_processed,metadata={'campaign_id':campaign.pk,'depth_limit':followup_depth,'page_limit':followup_limit,'remaining_queue':queued_remaining,'source_category':'forum','forum':True})

    return {
        'discovery_mode':mode,'forum_only':True,'primary_throughput_isolated':True,
        'execution_path':('Cloud Web · Forum idle pass' if mode=='cloud_web' else 'Local AI Discovery · Forum idle pass'),
        'providers':['Forum'],'queries':[],
        'cv_count':search_profile.get('cv_count',0),
        'top_profile_terms':[x['term'] for x in search_profile.get('skills',[])[:12] if isinstance(x,dict) and x.get('term')],
        'raw_hits':len(raw_records),'consolidated_hits':len(consolidated),
        'duplicates':max(0,len(raw_records)-len(consolidated))+int(lead_collector.get('duplicates') or 0),
        'unique':unique,'new_opportunities':unique,'opportunities_found':unique,
        'rediscovered_opportunities':max(0,len(opportunity_ids)-unique),'opportunity_ids':opportunity_ids,
        'leads_found':lead_collector['new'],'new_leads':lead_collector['new'],
        'rediscovered_leads':max(0,len(lead_collector['ids'])-int(lead_collector['new'] or 0)),
        'lead_ids':lead_collector['ids'],'errors':errors,'error_count':len(errors),
        'forum_discovery':{**(forum_meta or {}),'qualification_mode':mode,'qualified_cap':(cloud_cap if mode=='cloud_web' else local_cap)},
        'cloud_persistence_rejections':filter_collector if mode=='cloud_web' else {},
        'followup_discovery':{'pages_checked':followup_processed,'page_limit':followup_limit,'depth_limit':followup_depth,'queued_remaining':queued_remaining},
    }

def _market_specific_source_queries(markets, campaign, search_profile, limit=8):
    """Bounded site: queries for enabled sources that explicitly belong to a market."""
    roles=[str(x).strip() for x in re.split(r'[,;|\n]+',str(getattr(campaign,'role_families','') or '')) if str(x).strip()]
    skills=[str((x or {}).get('term') or '').strip() for x in (search_profile.get('skills') or []) if isinstance(x,dict) and str(x.get('term') or '').strip()]
    anchor=(roles or skills or ['hiring'])[0]
    out=[]; market_codes={m.code:m for m in markets}; by_market={code:[] for code in market_codes}
    for source in SearchSource.objects.filter(enabled=True).exclude(base_url='').order_by('-priority','name'):
        cfg=source.config_json if isinstance(source.config_json,dict) else {}
        codes=[str(x).lower() for x in (cfg.get('market_codes') or [])]
        try: domain=(urllib.parse.urlsplit(source.base_url).hostname or '').lower().removeprefix('www.')
        except Exception: domain=''
        if not domain: continue
        for code in codes:
            if code in by_market:
                by_market[code].append((source,domain)); break
    # Interleave one source per market before taking a second source for any market. The
    # market order rotates between runs, so a bounded source cap reaches every country
    # over time instead of repeatedly selecting the first alphabetic job boards.
    max_rows=max((len(rows) for rows in by_market.values()),default=0)
    for index in range(max_rows):
        for market in markets:
            rows=by_market.get(market.code) or []
            if index>=len(rows): continue
            source,domain=rows[index]
            out.append({'source_name':source.name,'domain':domain,'market':market,'query':f'site:{domain} "{anchor.replace(chr(34)," ")}"'})
            if len(out)>=limit: return out
    return out


_TRANSLATION_OPERATOR_RE=re.compile(r'(?i)\b(?:site|intitle|inurl|filetype|before|after):[^\s"]+')
_TRANSLATION_DOMAIN_RE=re.compile(r'(?i)(?<![\w@])(?:https?://[^\s"<>]+|www\.[a-z0-9.-]+|(?:[a-z0-9-]+\.)+[a-z]{2,})(?![\w@])')
_TRANSLATION_TECH_RE=re.compile(r'(?<!\w)(?:C\+\+|C#|\.NET|[A-Za-z0-9+.#-]*\d+[A-Za-z0-9+.#-]*|[A-Za-z]*[A-Z]{2,}[A-Za-z0-9+.#-]*)(?!\w)')
# Mixed/lowercase protocol and platform names do not always have punctuation, digits, or
# acronym casing. Keep a deliberately technical vocabulary exact as well; campaign planner
# one-token skill/product terms are additionally protected dynamically below.
_TRANSLATION_KNOWN_TECH_RE=re.compile(
    r'(?i)(?<![A-Za-z0-9_])(?:BACnet|Modbus|PROFINET|PROFIBUS|EtherCAT|CANopen|CANbus|MQTT|OPC(?:[ -]?UA)?|RTOS|FreeRTOS|Zephyr|QEMU|VMware|Docker|Kubernetes|Linux|OpenGL|Vulkan|CUDA|OpenCL|Qt)(?![A-Za-z0-9_])'
)


def _protect_query_translation_tokens(query, extra_terms=None):
    """Mask search syntax, domains and technical literals before translation."""
    text=str(query or '')
    spans=[]
    def add_span(start,end):
        if start>=end or any(not (end<=a or start>=b) for a,b in spans):
            return
        spans.append((start,end))
    for rx in (_TRANSLATION_OPERATOR_RE,_TRANSLATION_DOMAIN_RE,_TRANSLATION_TECH_RE,_TRANSLATION_KNOWN_TECH_RE):
        for m in rx.finditer(text):
            add_span(m.start(),m.end())
    for raw in extra_terms or []:
        term=' '.join(str(raw or '').split()).strip()
        if len(term)<2:
            continue
        # Planner terms are often specialist skills/products. Preserve a one-token skill
        # verbatim (Modbus, BACnet, Python, C++, CH375, etc.). Multi-word role phrases
        # remain translatable; their technical-looking sub-tokens are already caught by
        # the regex passes above.
        if not re.search(r'\s',term):
            for m in re.finditer(re.escape(term),text,flags=re.I):
                add_span(m.start(),m.end())
    mapping={}; masked=text
    # Replace right-to-left so source offsets stay valid. Placeholder numbering does
    # not carry meaning; it only gives us exact restoration anchors.
    for index,(start,end) in enumerate(sorted(spans,reverse=True)):
        token=f'ZXQSB{index}QXZ'
        mapping[token]=text[start:end]
        masked=masked[:start]+token+masked[end:]
    return masked,mapping


def _restore_query_translation_tokens(translated, mapping):
    text=str(translated or '')
    for token,value in mapping.items():
        match=re.search(re.escape(token),text,flags=re.I)
        if not match:
            return ''
        text=text[:match.start()]+value+text[match.end():]
    return text


_DETECTED_LANGUAGE_NAMES={
    'fr':'French','de':'German','es':'Spanish','pt':'Portuguese','it':'Italian','nl':'Dutch',
    'ja':'Japanese','jp':'Japanese','ko':'Korean','kr':'Korean','zh':'Chinese','zh-cn':'Chinese',
    'zh-tw':'Chinese','zh-hk':'Chinese','ms':'Malay','pl':'Polish','cs':'Czech','da':'Danish',
    'sv':'Swedish','no':'Norwegian','nb':'Norwegian','fi':'Finnish','ar':'Arabic','el':'Greek',
    'tr':'Turkish','he':'Hebrew','ru':'Russian','uk':'Ukrainian','vi':'Vietnamese','th':'Thai',
    'id':'Indonesian','hi':'Hindi','bn':'Bengali','ur':'Urdu','fa':'Persian','bg':'Bulgarian',
    'ro':'Romanian','hu':'Hungarian','hr':'Croatian','sr':'Serbian','sk':'Slovak','sl':'Slovenian',
    'et':'Estonian','lv':'Latvian','lt':'Lithuanian','ka':'Georgian','hy':'Armenian','az':'Azerbaijani',
    'kk':'Kazakh','uz':'Uzbek','ne':'Nepali','km':'Khmer','lo':'Lao','my':'Burmese','mn':'Mongolian',
    'sw':'Swahili','bs':'Bosnian','ta':'Tamil','si':'Sinhala',
}

def _translation_language_for_result(result, detected_code=''):
    """Choose a translation language from explicit, market, then detector evidence.

    Translation eligibility follows the page we actually found, not whether the search
    query happened to be one of the small explicitly multilingual query assignments.
    """
    explicit=' '.join(str((result or {}).get('_multilingual_language') or '').split())
    if explicit:
        return explicit[:40], 'query'
    market_code=str((result or {}).get('_discovery_market_code') or '').strip().lower()
    market=MARKET_BY_CODE.get(market_code)
    if market:
        for language in market.languages:
            if str(language).strip().casefold()!='english':
                return str(language).strip()[:40], 'market'
    code=str(detected_code or '').strip().lower().replace('_','-')
    name=_DETECTED_LANGUAGE_NAMES.get(code) or _DETECTED_LANGUAGE_NAMES.get(code.split('-',1)[0])
    if name:
        return name, 'detector'
    return (code[:16] if code and code not in {'en','eng','english'} else ''), ('detector' if code else '')


def _translate_multilingual_page(page_text, language, source_url=''):
    """Translate a relevant foreign-language page for the same strict local gates."""
    text=' '.join(str(page_text or '').split())[:16000]
    language=' '.join(str(language or '').split())[:40]
    if not text or not language: return ''
    try:
        from .ai import generate
        translated=str(generate(
            'Translate the following employment opportunity page faithfully into English. '
            'Preserve company names, role titles, dates, locations, compensation, requirements, '
            'application instructions, URLs and uncertainty. Do not add facts or recommendations. '
            'Return only the English interpretation.\n\n'
            f'Language: {language}\nSource: {source_url[:1000]}\n\n{text}',
            stage='first_filter',timeout=75,
            subject={'type':'multilingual_source','id':'','label':f'{language} source interpretation'},
        ) or '').strip()
    except Exception:
        return ''
    if len(translated)<80 or not primarily_english(translated,'en'): return ''
    return translated



def _google_jobs_query_text(query_item):
    """Build a SearchAPI Google Jobs query without generic-web operators/geography.

    Google Jobs has dedicated ``location``, ``gl`` and ``hl`` request parameters. Source
    planner ``site:`` scopes and ScoutBox's appended market/city text belong to ordinary
    web search and materially reduce Google Jobs recall, so keep only the role/skill intent.
    """
    item=query_item if isinstance(query_item,dict) else {}
    raw=str(item.get('provider_query') or item.get('base_query') or item.get('query') or '').strip()
    # Remove web-search-only operators. Preserve quoted role/skill phrases and ordinary
    # words; SearchAPI Google Jobs supports natural-language q rather than generic SERP
    # site scoping for ScoutBox's acquisition design.
    raw=re.sub(r'(?i)\bsite:\S+',' ',raw)
    raw=re.sub(r'(?i)\b(?:inurl|intitle|intext|filetype):\S+',' ',raw)
    raw=re.sub(r'\s+',' ',raw).strip(' ,;|')
    # Defensive quote repair for multilingual/model-generated text so an unmatched quote
    # cannot poison the provider request.
    if raw.count('"') % 2:
        raw=raw.replace('"','')
    return raw[:300]


def _provider_query_text(provider, query_item):
    if str(getattr(provider,'name','') or '')=='SearchAPI · Google Jobs':
        return _google_jobs_query_text(query_item)
    return str((query_item or {}).get('query') or '').strip()

def _multilingual_query_items(cfg, query_items, markets, *, rotation_offset=0):
    """Create a very small optional translated-query slice; failures simply skip it."""
    assignments=multilingual_assignments(cfg,markets,rotation_offset=rotation_offset)
    if not assignments: return []
    out=[]
    for idx,assignment in enumerate(assignments):
        item=query_items[idx%len(query_items)] if query_items else {}
        market=assignment['market']; language=assignment['language']
        source_q=str(item.get('base_query') or item.get('query') or '').strip()
        if not source_q: continue
        translated=''; translation_error=''
        protected_query,protected_tokens=_protect_query_translation_tokens(source_q,item.get('terms') or [])
        try:
            from .ai import generate
            translated=str(generate(
                f'Translate only the natural-language words in this employment/company discovery search query into {language}. '
                'Tokens shaped like ZXQSB0QXZ are protected placeholders: copy every one exactly and do not translate, move, split or remove it. '
                'Preserve search operators and balanced quotation marks. Return only the translated query, no explanation.\n\n'+protected_query,
                stage='query_planning',timeout=45,subject={'type':'campaign','id':'','label':'Multilingual discovery'}
            ) or '').strip()[:300]
            translated=_restore_query_translation_tokens(translated,protected_tokens)
            translated=re.sub(r'\s+',' ',translated).strip()
            # Model translation occasionally drops one side of a quoted phrase. An
            # unbalanced quote changes the whole provider parse, so degrade safely to
            # the same words without quote operators rather than issuing a malformed query.
            if translated.count('\"') % 2:
                translated=translated.replace('\"','')
            try:
                from .query_normalizer import normalize_generated_search_query
                translated=normalize_generated_search_query(translated)
            except Exception:
                translated=re.sub(r'\s+',' ',translated).strip()
        except Exception as exc:
            translation_error=str(exc)[:300]; translated=''
        try:
            UsageMetric.objects.create(
                category='discovery_market',provider='query_planner',stage='multilingual_translation',requests=1,pages=1 if translated else 0,errors=0 if translated else 1,
                metadata={'language':language,'market_code':getattr(market,'code',''),'market':getattr(market,'name',''),'source':assignment.get('source',''),'source_query':source_q[:300],'translated_query':translated[:300],'error':translation_error},
            )
        except Exception:
            pass
        if translated:
            row=dict(item); row['base_query']=source_q; row['provider_query']=translated; row['query']=market_query(translated,market,rotation_offset=rotation_offset+idx); row['market']=market_search_meta(market); row['multilingual_language']=language; row['multilingual_id']=assignment['id']; row['multilingual_source']=assignment['source']; row['kind']='multilingual-'+str(row.get('kind') or 'query'); out.append(row)
    return out


def run_campaign(campaign, test=False, progress_callback=None, should_stop=None, rotation_offset=0, discovery_mode=None, forum_only=False):
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    _check_stop(should_stop); _progress(progress_callback,5,'Building discovery plan')

    # Discovery Method is a hard execution contract. A queued run can pass its snapped
    # mode so later settings edits cannot silently change how that run executes.
    mode=str(discovery_mode or cfg.discovery_mode or 'source_guided').strip().lower()
    if forum_only:
        if mode=='cloud_web':
            try:
                if not has_usable_cloud_web_model():
                    raise RuntimeError('One or more Cloud Web stages is not configured.')
                cloud_discovery_route(stage='url_scrape')
            except Exception as exc:
                raise CloudWebUnavailable('Cloud Web unavailable — no usable Cloud provider/model') from exc
        return _run_forum_only_campaign(campaign,cfg,test=test,progress_callback=progress_callback,should_stop=should_stop,discovery_mode=mode)
    if mode == 'cloud_web':
        try:
            if not has_usable_cloud_web_model():
                raise RuntimeError('One or more Cloud Web stages is not configured.')
            cloud_discovery_route(stage='url_scrape')
        except Exception as exc:
            raise CloudWebUnavailable('Cloud Web unavailable — no usable Cloud provider/model') from exc
        return _run_cloud_native_campaign(campaign,cfg,test=test,progress_callback=progress_callback,should_stop=should_stop)
    if mode != 'source_guided':
        raise RuntimeError(f'Unknown discovery mode: {mode}')

    _check_stop(should_stop); _progress(progress_callback,10,'Selecting search providers')
    providers,provider_selection=provider_selection_details(limit=4)
    query_cap=campaign.queries_per_rotation or cfg.keywords_per_run
    plan=build_campaign_query_plan(campaign,max_queries=min(query_cap,4 if test else query_cap),rotation_offset=rotation_offset)
    query_items=list(plan.get('queries') or [])
    if not query_items:
        raise RuntimeError('Candidate Profile does not contain enough reliable role/skill evidence to build discovery queries. Review Resume concepts / likely roles, then run again.')
    coverage=market_plan(cfg,campaign_id=getattr(campaign,'pk',0),rotation_offset=rotation_offset)
    markets=coverage['markets']
    from .discovery_markets import market_workload_schedule
    scheduled_markets=market_workload_schedule(coverage,len(query_items),rotation_offset=rotation_offset)
    for idx,item in enumerate(query_items):
        market=scheduled_markets[idx] if idx<len(scheduled_markets) else (markets[idx % len(markets)] if markets else None)
        item['base_query']=item.get('query','')
        item['provider_query']=item.get('base_query','')
        if market:
            item['query']=market_query(item.get('query',''),market,rotation_offset=rotation_offset+idx); item['market']=market_search_meta(market)
    multilingual_items=_multilingual_query_items(cfg,query_items,markets,rotation_offset=rotation_offset)
    query_items.extend(multilingual_items)
    queries=[x['query'] for x in query_items]
    raw_records=[]; errors=[]; multilingual_executed=set(); market_query_executions={}; facebook_enabled=SearchSource.objects.filter(name='Facebook public posts',enabled=True).exists()
    if facebook_enabled:
        try:
            fb_revalidation=revalidate_facebook_pages(limit=2 if test else 8,max_age_days=7)
            if fb_revalidation.get('removed'):
                errors.append(f"Facebook Pages to Watch cleanup removed {fb_revalidation['removed']} confirmed irrelevant page(s).")
        except Exception as exc:
            errors.append(f'Facebook Pages to Watch revalidation: {exc}')
    # Forum browsing is intentionally not inline. It is scheduled on a dedicated, idle-only
    # queue so forum latency can never delay normal search-engine or direct-source work.
    forum_meta={'executed':False,'isolated':True,'reason':'Forum discovery runs independently on the forum queue only when primary discovery is idle.'}
    direct_records=[]; direct_errors=[]; direct_meta={}
    facebook_cfg=FacebookConfig.objects.get_or_create(pk=1)[0]

    try:
        local_search_stage_budget=max(120,min(1800,int(os.environ.get('SCOUTBOX_LOCAL_SEARCH_STAGE_MAX_SECONDS','600') or 600)))
    except Exception:
        local_search_stage_budget=600
    try:
        per_provider_stage_budget=max(60,min(900,int(os.environ.get('SCOUTBOX_SEARCH_PROVIDER_STAGE_MAX_SECONDS','180') or 180)))
    except Exception:
        per_provider_stage_budget=180
    provider_error_limit=_search_provider_error_limit()
    search_stage_started=time.monotonic()
    provider_total=max(1,len(providers))
    for provider_idx,provider in enumerate(providers,1):
        if local_search_stage_budget and time.monotonic()-search_stage_started>local_search_stage_budget:
            errors.append(f'Local search-engine stage time budget reached after {provider_idx-1}/{provider_total} providers; remaining providers will rotate into later runs.')
            break
        _check_stop(should_stop); _progress(progress_callback,15+int(30*(provider_idx-1)/provider_total),f'Searching with {provider.name}')
        try:
            configured_provider_cap=max(1,int(cfg.queries_per_provider or 1))
        except Exception:
            configured_provider_cap=1
        provider_query_cap=provider_query_allowance(provider,configured_provider_cap)
        # Re-check remaining provider budget at execution time. Selection happens before
        # the campaign loop and another worker may consume quota meanwhile; bounding the
        # actual slice prevents a late run from overshooting paid/API daily limits.
        try:
            provider_query_cap=min(provider_query_cap,max(0,int(provider_budget_remaining(provider))))
        except Exception:
            pass
        if provider_query_cap<=0:
            errors.append(f'{provider.name}: daily provider budget exhausted before this campaign slice began.')
            continue
        if test:
            provider_query_cap=min(provider_query_cap,2)
        per_provider=0; multilingual_provider_queries=0; provider_started=time.monotonic(); consecutive_errors=0
        for query_item in query_items:
            q=_provider_query_text(provider,query_item); market_info=query_item.get('market') or {}; market=MARKET_BY_CODE.get(str(market_info.get('market_code') or ''))
            if not provider_market_compatible(provider,market):
                continue
            is_multilingual=bool(query_item.get('multilingual_id'))
            _check_stop(should_stop)
            if is_multilingual and multilingual_provider_queries>=len(multilingual_items): continue
            if not is_multilingual and per_provider>=provider_query_cap: continue
            if per_provider_stage_budget and time.monotonic()-provider_started>per_provider_stage_budget:
                errors.append(f'{provider.name}: provider search time budget reached; remaining queries will rotate into later runs.')
                break
            if local_search_stage_budget and time.monotonic()-search_stage_started>local_search_stage_budget:
                errors.append('Local search-engine stage time budget reached; remaining queries will rotate into later runs.')
                break
            search_progress=15+int(30*(provider_idx-1)/provider_total)
            search_message=f'Searching {provider.name}: {q}'
            planned_query_language=str(query_item.get('multilingual_language') or 'English').strip() or 'English'
            results,err=_search_source_with_liveness(provider,q,6 if test else cfg.max_results_per_query,progress_callback,search_progress,search_message,should_stop,market=market,query_language=planned_query_language)
            if is_multilingual:
                multilingual_provider_queries+=1; multilingual_executed.add(query_item.get('multilingual_id'))
            else:
                per_provider+=1
            if market_info.get('market_code'):
                code=market_info.get('market_code'); market_query_executions[code]=market_query_executions.get(code,0)+1
                UsageMetric.objects.create(category='discovery_market',provider=provider.name,stage='query',requests=1,pages=len(results or []),errors=1 if err else 0,metadata={'market_code':market_info.get('market_code'),'market':market_info.get('market',''),'multilingual_language':query_item.get('multilingual_language',''),'multilingual':is_multilingual})
            if err:
                consecutive_errors+=1
                errors.append(f'{provider.name}: {err}')
                if consecutive_errors>=provider_error_limit:
                    errors.append(f'{provider.name}: stopped after {consecutive_errors} consecutive request errors; remaining queries will rotate into later runs.')
                    break
                continue
            consecutive_errors=0
            for r in results:
                r=dict(r); r['_discovery_market']=market_info.get('market',''); r['_discovery_market_code']=market_info.get('market_code',''); r['_multilingual_language']=query_item.get('multilingual_language',''); r['_multilingual_source']=query_item.get('multilingual_source','')
                raw_records.append({'result':r,'source':provider,'query':q})
            if not is_multilingual and provider.name!='SearchAPI · Google Jobs' and facebook_enabled and facebook_cfg.use_search_index and cfg.feature_facebook_index_search and per_provider<provider_query_cap:
                if per_provider_stage_budget and time.monotonic()-provider_started>per_provider_stage_budget:
                    errors.append(f'{provider.name}/Facebook index: provider search time budget reached.')
                    break
                fq=facebook_index_queries(q)[per_provider % 3]
                fb_message=f'Searching {provider.name}: {fq}'
                fbres,fberr=_search_source_with_liveness(provider,fq,min(4,cfg.max_results_per_query),progress_callback,search_progress,fb_message,should_stop,market=market,query_language='English'); per_provider+=1
                if fberr:
                    consecutive_errors+=1
                    errors.append(f'{provider.name}/Facebook index: {fberr}')
                    if consecutive_errors>=provider_error_limit:
                        errors.append(f'{provider.name}: stopped after {consecutive_errors} consecutive request errors; remaining queries will rotate into later runs.')
                        break
                else:
                    consecutive_errors=0
                for r in fbres:
                    r['facebook_mode']='search-index'; remember_facebook_page(r); raw_records.append({'result':r,'source':provider,'query':fq})

    # Direct adapters are valuable supplementary acquisition, but they run only after the
    # primary search-engine slice and under their own wall-clock/source caps. This prevents
    # a slow feed/API adapter from reducing search-engine coverage for the run.
    try:
        direct_stage_budget=max(20,min(300,int(os.environ.get('SCOUTBOX_DIRECT_SOURCE_STAGE_MAX_SECONDS','60') or 60)))
    except Exception:
        direct_stage_budget=60
    try:
        direct_source_cap=max(2,min(16,int(os.environ.get('SCOUTBOX_DIRECT_SOURCE_MAX_SOURCES','6') or 6)))
    except Exception:
        direct_source_cap=6
    _progress(progress_callback,41,'Checking fresh direct sources')
    direct_records,direct_errors,direct_meta=non_forum_direct_source_rows(
        campaign,plan.get('search_profile') or {},limit=(16 if test else min(36,max(20,int(cfg.max_results_per_query or 100)//3))),
        test=test,progress_callback=progress_callback,should_stop=should_stop,
        stage_budget_seconds=(30 if test else direct_stage_budget),max_sources=(3 if test else direct_source_cap),
    )
    raw_records.extend(direct_records); errors.extend(direct_errors)

    # One bounded market-localized Forums query and one News query per Local campaign.
    # These lanes are supplemental: they cannot displace Google Jobs/Web or ordinary SERP
    # coverage, and their non-vacancy output is routed to Hidden Leads as hiring signals.
    signal_records,signal_errors,signal_meta=_searchapi_signal_records(
        campaign,cfg,plan.get('search_profile') or {},markets,test=test,
        progress_callback=progress_callback,should_stop=should_stop,rotation_offset=rotation_offset,
    )
    raw_records.extend(signal_records); errors.extend(signal_errors)

    direct_search_meta={'provider':'','requests':0,'raw_results':0,'sources':[],'passes':[]}
    if providers:
        # Generic direct-source fallback queries do not carry a Discovery Market, so never
        # send them to SearchAPI: SearchAPI intentionally refuses unlocalized requests to
        # prevent Google's implicit US default. Keep these on an ordinary global provider.
        generic_queries=_direct_source_search_queries(campaign,direct_meta,plan.get('search_profile') or {})
        generic_provider=next((p for p in providers if not p.name.startswith('SearchAPI ·')),None)
        if generic_provider and generic_queries:
            rows,errs,meta=_required_direct_source_search_records(
                generic_provider,generic_queries,cfg,test=test,progress_callback=progress_callback,should_stop=should_stop,progress_base=42
            )
            raw_records.extend(rows); errors.extend(errs); direct_search_meta['passes'].append(meta)
            direct_search_meta['requests']+=int(meta.get('requests') or 0); direct_search_meta['raw_results']+=int(meta.get('raw_results') or 0); direct_search_meta['sources']+=list(meta.get('sources') or [])

        # Market-specific local-board queries are the opposite: prefer SearchAPI Google Web
        # because it can enforce country/language/location at the provider layer. This turns
        # sources such as SEEK, Reed, JobsDB and JobStreet into genuinely localized discovery
        # even when their own category/search pages reject ScoutBox's direct fetches.
        try:
            market_source_cap=max(4,min(32,int(os.environ.get('SCOUTBOX_MARKET_SOURCE_QUERIES_PER_RUN','16') or 16)))
        except Exception:
            market_source_cap=16
        market_queries=[]
        for direct_idx,row in enumerate(_market_specific_source_queries(markets,campaign,plan.get('search_profile') or {},limit=(3 if test else market_source_cap))):
            market_queries.append({'source_name':row['source_name'],'domain':row['domain'],'query':market_query(row['query'],row['market'],rotation_offset=rotation_offset+direct_idx),'market':market_search_meta(row['market'])})
        market_provider=next((p for p in providers if p.name=='SearchAPI · Google Web'),None)
        if market_provider is None:
            market_provider=next((p for p in providers if p.name!='SearchAPI · Google Jobs'),None)
        if market_provider and market_queries:
            rows,errs,meta=_required_direct_source_search_records(
                market_provider,market_queries,cfg,test=test,progress_callback=progress_callback,should_stop=should_stop,progress_base=44
            )
            raw_records.extend(rows); errors.extend(errs); direct_search_meta['passes'].append(meta)
            direct_search_meta['requests']+=int(meta.get('requests') or 0); direct_search_meta['raw_results']+=int(meta.get('raw_results') or 0); direct_search_meta['sources']+=list(meta.get('sources') or [])
        direct_search_meta['provider']=' + '.join(dict.fromkeys(str(x.get('provider') or '') for x in direct_search_meta['passes'] if x.get('provider')))

    career_records,career_errors,career_meta=_company_career_page_records(
        campaign,providers,plan.get('search_profile') or {},cfg,test=test,progress_callback=progress_callback,should_stop=should_stop
    )
    raw_records.extend(career_records); errors.extend(career_errors)

    if not providers and raw_records:
        message=_search_engine_unavailable_error(provider_selection)
        errors.append(message); _record_search_engine_unavailable(message)

    if not providers and not raw_records:
        exhausted=provider_selection.get('budget_exhausted') or []
        usable_count=int(provider_selection.get('usable_count') or 0)
        if usable_count and exhausted:
            raise SearchProvidersUnavailable(
                'provider_daily_budgets_exhausted',
                'Waiting · Search provider daily budgets exhausted',
                provider_selection,
            )
        raise SearchProvidersUnavailable(
            'no_eligible_search_providers',
            'Waiting · No eligible search provider is configured',
            provider_selection,
        )

    # Official Graph path uses the strongest Resume-derived concepts rather than a manually maintained keyword list.
    if facebook_enabled:
        terms=[x['term'] for x in plan['search_profile'].get('skills',[])[:8]]
        fb,fb_errors=facebook_graph_posts(terms,limit=12 if test else 25)
        errors.extend(fb_errors)
        fbsource=SearchSource.objects.filter(name='Facebook public posts').first()
        if fbsource:
            raw_records.extend({'result':r,'source':fbsource,'query':'Facebook Graph Resume-derived Page watch'} for r in fb)

    _check_stop(should_stop); _progress(progress_callback,48,'Expanding aggregate job pages')
    expanded=[]
    for rec in raw_records:
        expanded.extend(_expand_aggregate_record(rec))
    raw_records=expanded
    _check_stop(should_stop); _progress(progress_callback,50,'Consolidating and deduplicating results')
    consolidated=consolidate_results(raw_records,plan['search_profile'])
    consolidated,market_domain_dropped=_limit_job_board_candidates(consolidated,per_board=(6 if test else 12))
    unique=0; opportunity_ids=[]; lead_collector={'ids':[],'new':0,'duplicates':0}
    followup_limit=max(0,min(250,int(getattr(cfg,'followup_pages_per_run',50) or 0)))
    followup_depth=max(0,min(5,int(getattr(cfg,'followup_link_depth',3) or 0)))
    followups={'queue':[],'seen':set(),'max_depth':followup_depth}
    for rec in raw_records:
        try:
            u=canonical(str((rec.get('result') or {}).get('url') or ''))
            if u: followups['seen'].add(u)
        except Exception: pass
    total=max(1,len(consolidated))
    for idx,item in enumerate(consolidated,1):
        _check_stop(should_stop); _progress(progress_callback,50+int(35*idx/total),f'Analysing candidate {idx}/{total}')
        primary=item.pop('_source_obj')
        primary_query=(item.get('_provenance') or [{}])[0].get('query','')
        opp,isnew=ingest_result(item,primary,campaign,primary_query,lead_collector=lead_collector,search_profile=plan['search_profile'],followup_collector=followups if followup_limit and followup_depth else None,followup_depth=0); unique+=int(isnew)
        if opp and item.get('_discovery_market_code'):
            UsageMetric.objects.create(category='discovery_market',provider=primary.name if primary else '',stage='retained',pages=1,metadata={'market_code':item.get('_discovery_market_code'),'market':item.get('_discovery_market',''),'multilingual_language':item.get('_multilingual_language',''),'opportunity_id':opp.pk})
        if opp and opp.pk not in opportunity_ids: opportunity_ids.append(opp.pk)

    # Local-only bounded link frontier. Each downloaded page can contribute relevant links,
    # but the run-level page cap and depth cap prevent uncontrolled crawling/topic drift.
    followup_processed=0
    while followup_limit and followup_depth and followups['queue'] and followup_processed<followup_limit:
        _check_stop(should_stop)
        rec=followups['queue'].pop(0); depth=int(rec.get('depth') or 1)
        if depth>followup_depth: continue
        followup_processed+=1
        _progress(progress_callback,85+int(12*followup_processed/max(1,followup_limit)),f'Checking follow-up page {followup_processed}/{followup_limit} · depth {depth}/{followup_depth}')
        item=dict(rec.get('result') or {}); primary=rec.get('source'); q=rec.get('query') or 'Local follow-up link'
        try:
            opp,isnew=ingest_result(item,primary,campaign,q,lead_collector=lead_collector,search_profile=plan['search_profile'],followup_collector=followups,followup_depth=depth)
            unique+=int(isnew)
            if opp and opp.pk not in opportunity_ids: opportunity_ids.append(opp.pk)
        except Exception as exc:
            errors.append(f'Local follow-up {item.get("url","")[:180]}: {exc}')
    if followup_processed:
        UsageMetric.objects.create(category='followup_discovery',provider='Local Direct Search',stage='bounded_followup',requests=followup_processed,pages=followup_processed,metadata={'campaign_id':campaign.pk,'depth_limit':followup_depth,'page_limit':followup_limit,'remaining_queue':len(followups['queue'])})

    campaign.last_run=timezone.now(); campaign.save(update_fields=['last_run'])
    return {
        'discovery_mode':'source_guided',
        'execution_path':'Local AI Discovery · Search Sources + Ollama',
        'providers':[p.name for p in providers],
        'provider_selection':provider_selection,
        'queries':queries,
        'query_details':query_items,
        'discovery_markets':[m.name for m in markets],
        'market_coverage':{**{k:v for k,v in coverage.items() if k!='markets'},'allocation':market_query_executions},
        'multilingual_exploration':{'enabled':True,'languages':auto_multilingual_languages(cfg),'strength':getattr(cfg,'multilingual_exploration_strength','balanced'),'planned':len(multilingual_items),'executed':len(multilingual_executed),'executed_ids':sorted(multilingual_executed)},
        'cv_count':plan['search_profile'].get('cv_count',0),
        'top_profile_terms':[x['term'] for x in plan['search_profile'].get('skills',[])[:12]],
        'raw_hits':len(raw_records),
        'consolidated_hits':len(consolidated),
        'duplicates_merged_before_enrichment':max(0,len(raw_records)-len(consolidated)-int(market_domain_dropped or 0)),
        'job_board_candidates_dropped':int(market_domain_dropped or 0),
        'duplicates':max(0,len(raw_records)-len(consolidated)-int(market_domain_dropped or 0))+int(lead_collector.get('duplicates') or 0),
        'unique':unique,
        'new_opportunities':unique,
        'opportunities_found':unique,
        'rediscovered_opportunities':max(0,len(opportunity_ids)-unique),
        'opportunity_ids':opportunity_ids,
        'leads_found':lead_collector['new'],
        'new_leads':lead_collector['new'],
        'rediscovered_leads':max(0,len(lead_collector['ids'])-int(lead_collector['new'] or 0)),
        'lead_ids':lead_collector['ids'],
        'errors':errors,
        'error_count':len(errors),
        'location_policy':plan['location_policy'],
        'fresh_source_discovery':direct_meta,
        'supplemental_signal_discovery':signal_meta,
        'forum_discovery':forum_meta,
        'parallel_direct_source_search':direct_search_meta,
        'company_career_pages':career_meta,
        'followup_discovery':{'pages_checked':followup_processed,'page_limit':followup_limit,'depth_limit':followup_depth,'queued_remaining':len(followups['queue'])},
        'fresh_source_errors':direct_errors,
    }
