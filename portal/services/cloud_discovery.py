import hashlib
import json
import re
from urllib.parse import urlsplit

from django.db.models import Q
from django.utils import timezone

from portal.ui import COUNTRIES
from portal.models import (
    CompanyLead, Contact, Profile, SearchProviderStat, SearchSource, PortalSettings,
    CloudRunUsage, CustomSearchDomain, UsageMetric,
)
from .discovery_markets import market_plan, multilingual_assignments
from .ai import (
    cloud_web_search, web_search_with, effective_cloud_bundle_anchor,
    generate_with, generate_with_route, cloud_discovery_route,
)
from .blacklist import is_blacklisted_url
from .cloud_budget import mark_candidates, CloudLimitReached, scoped_usage_context, usage_context
from .opportunity_urls import is_generic_opportunity_collection_url, looks_like_specific_opportunity_url, is_disallowed_adult_url
from .pagefetch import fetch_target
from .dedup import active_duplicate_lead, active_opportunity_for_company, clean_contact_name
from .mailbox import automatic_addressbook_contact_allowed, broad_shared_contact_allowed, is_region_routing_address, assignable_contact_email, contact_email_has_non_contact_context, clean_contact_email, maybe_persist_addressbook_contact
from .queryplanner import extract_active_cv_texts
from .company_research import company_summary_from_intel
from .search import is_search_engine_url, unwrap_search_result_url
from .campaign_links import attribute_campaign
from .content_quality import adult_content_reason
from .cold import hidden_lead_minibrowser_admission, strip_hidden_lead_evidence_markers
from .selectivity import current as selectivity_current, opportunity_thresholds, lead_policy, specialist_alignment, campaign_alignment, instruction as selectivity_instruction

REMOTE_ACCEPTED = {'fully_remote', 'remote'}
_EMAIL_RE = re.compile(r'(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])', re.I)
_URL_RE = re.compile(r'https?://[^\s<>()\[\]{}\"\']+', re.I)


def _extract_json(text):
    text = (text or '').strip()
    candidates = [text]
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.I | re.S)
    if m:
        candidates.insert(0, m.group(1).strip())
    first = text.find('{')
    last = text.rfind('}')
    if first >= 0 and last > first:
        candidates.append(text[first:last + 1])
    for raw in candidates:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {'results': data}
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _sources(row, meta):
    out = []
    raw = row.get('sources') or row.get('evidence_urls') or []
    if isinstance(raw, str):
        raw = [raw]
    for item in raw:
        u = str((item.get('url') or item.get('uri')) if isinstance(item, dict) else item or '').strip()
        if u.startswith(('http://', 'https://')) and u not in out:
            out.append(u)
    for u in (meta.get('sources') or []):
        u = str(u or '').strip()
        if u.startswith(('http://', 'https://')) and u not in out:
            out.append(u)
    return out[:40]


def _normalized_contact_url(url):
    raw = str(url or '').strip().rstrip('.,;:!?)]}')
    if not raw.startswith(('http://', 'https://')):
        return ''
    try:
        parts = urlsplit(raw)
        host = parts.netloc.lower().removeprefix('www.')
        path = re.sub(r'/+', '/', parts.path or '/').rstrip('/') or '/'
        return f'{host}{path}'.casefold()
    except Exception:
        return raw.rstrip('/').casefold()


def _lead_outreach_note(row, lead_url=''):
    """Return only concrete outreach data that adds to the lead target.

    Cloud qualification often returns prose such as "reach out via the contact form".
    That is not useful as a saved note by itself. Keep only an actual public email or
    a distinct direct-contact URL, and render it as compact factual data rather than
    model-generated outreach advice.
    """
    path = str((row or {}).get('_contact_path') or '').strip()
    emails = []
    for value in list((row or {}).get('_validated_emails') or []) + _EMAIL_RE.findall(path):
        email = str(value or '').strip().lower().strip('.,;:<>[]()')
        if email and email not in emails and not _cloud_contact_noise(email):
            emails.append(email)

    lead_key = _normalized_contact_url(lead_url)
    urls = []
    for raw in _URL_RE.findall(path):
        url = str(raw or '').strip().rstrip('.,;:!?)]}')
        key = _normalized_contact_url(url)
        if not key or key == lead_key or any(key == _normalized_contact_url(x) for x in urls):
            continue
        urls.append(url)

    parts = []
    if emails:
        parts.append('Email: ' + ', '.join(emails[:3]))
    for url in urls[:2]:
        label = 'Contact form' if ('contact' in url.casefold() or 'contact form' in path.casefold()) else 'Contact link'
        parts.append(f'{label}: {url}')
    return ' · '.join(parts)[:1400]


def _lead_contact_url(row, lead_url=''):
    """Return one direct public contact URL that adds to the lead URL."""
    path = str((row or {}).get('_contact_path') or '').strip()
    lead_key = _normalized_contact_url(lead_url)
    for raw in _URL_RE.findall(path):
        url = str(raw or '').strip().rstrip('.,;:!?)]}')
        key = _normalized_contact_url(url)
        if key and key != lead_key:
            return url[:1000]
    return ''


def _merge_generated_lead_note(existing, generated):
    existing = str(existing or '').strip()
    generated = str(generated or '').strip()
    if not generated:
        return existing
    if generated.casefold() in existing.casefold():
        return existing
    return (existing + ('\n' if existing else '') + generated)[:4000]


def _int(value, default=0, lo=0, hi=100):
    try:
        value = float(value)
        # Older responses sometimes used confidence 0..1.
        if hi == 100 and 0 < value <= 1:
            value *= 100
        return max(lo, min(hi, int(round(value))))
    except Exception:
        return default


def _bool(value):
    return value is True or str(value or '').strip().lower() in {'1', 'true', 'yes', 'explicit'}


def _structured_country_from_text(value):
    raw=' '.join(str(value or '').split()).strip()
    if not raw or raw[0] not in '[{':
        return None
    try:
        parsed=json.loads(raw)
    except Exception:
        return ''
    aliases={
        'US':'United States','USA':'United States','U.S.':'United States','U.S.A.':'United States','United States of America':'United States',
        'GB':'United Kingdom','GBR':'United Kingdom','UK':'United Kingdom','U.K.':'United Kingdom','Great Britain':'United Kingdom','Britain':'United Kingdom',
        'Republic of Korea':'South Korea','Korea, Republic of':'South Korea',
    }
    found=[]
    def add(candidate):
        token=' '.join(str(candidate or '').split()).strip(' \"\'.:,;{}[]()')
        if not token:
            return
        token=aliases.get(token,aliases.get(token.upper(),token))
        for country in COUNTRIES:
            if token.casefold()==country.casefold() and country not in found:
                found.append(country)
                return
    def walk(obj):
        if isinstance(obj,dict):
            typ=str(obj.get('@type') or obj.get('type') or '').casefold()
            if 'country' in typ:
                add(obj.get('name') or obj.get('alternateName'))
            for key in ('addressCountry','country','countryCode'):
                if key in obj:
                    val=obj.get(key)
                    if isinstance(val,(dict,list)):
                        walk(val)
                    else:
                        add(val)
            for val in obj.values():
                if isinstance(val,(dict,list)):
                    walk(val)
        elif isinstance(obj,list):
            for item in obj:
                walk(item)
        elif isinstance(obj,str):
            add(obj)
    walk(parsed)
    return found[0] if len(found)==1 else ''


def _clean_company_country(value):
    """Return an actual company/HQ location, never a remote-work eligibility label or raw JSON."""
    structured=_structured_country_from_text(value)
    if structured is not None:
        return structured
    text=' '.join(str(value or '').split()).strip()[:120]
    low=text.casefold()
    if not text:
        return ''
    remote_markers=('remote worldwide','worldwide remote','fully remote','remote / worldwide','remote/anywhere','remote anywhere','home based','home-based','remote / distributed','distributed team','global remote')
    if any(marker in low for marker in remote_markers):
        return ''
    if low in {'remote','worldwide','global','anywhere','distributed','remote worldwide','remote / distributed'}:
        return ''
    return text


def _provider_response_truncated(metadata):
    """Read provider-native finish state from the web-search response metadata."""
    raw = (metadata or {}).get('raw') or {}
    provider = str((metadata or {}).get('provider') or '').lower()
    try:
        if provider == 'gemini':
            return any(str(c.get('finishReason') or '').upper() in {'MAX_TOKENS', 'LENGTH'} for c in (raw.get('candidates') or []) if isinstance(c, dict))
        if provider == 'openrouter':
            return any(str(c.get('finish_reason') or '').lower() in {'length', 'max_tokens'} for c in (raw.get('choices') or []) if isinstance(c, dict))
        if provider == 'openai':
            return str(raw.get('status') or '').lower() in {'incomplete', 'truncated'}
    except Exception:
        return False
    return False


def _campaign_list(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in re.split(r'[,\n;|]+', str(value or '')) if x.strip()]


def _operating_locations(profile, campaign):
    values = list(profile.operating_locations or [])
    if profile.operating_location and profile.operating_location not in values:
        values.append(profile.operating_location)
    for value in (campaign.locations or []):
        if value and value not in values:
            values.append(value)
    return values[:8]


def _soft_preferences(profile, campaign):
    scope = dict(profile.scope_json or {})
    engagement = _campaign_list(campaign.engagement_types) or [str(x) for x in (scope.get('engagement') or [])]
    sizes = _campaign_list(campaign.company_sizes) or [str(x) for x in (scope.get('company_size') or [])]
    return {
        'locations': _operating_locations(profile, campaign),
        'engagement': engagement[:10],
        'company_sizes': sizes[:10],
        'exclude_marketplaces': bool(scope.get('exclude_marketplaces', True)),
    }


def _brief_cache_key(role, docs, profile, campaign):
    payload = {
        'role': str(role or '').strip().lower(),
        'docs': [(d.get('id'), hashlib.sha256((d.get('text') or '').encode('utf-8', 'ignore')).hexdigest()) for d in docs],
        'high': profile.high_priority_text or '',
        'medium': profile.medium_priority_text or '',
        # campaign technologies are steering evidence for choosing the best CV, not model-facing discovery dump
        'technologies': _campaign_list(campaign.technologies),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _fallback_cv_selection(role, docs, campaign):
    """Content-only fallback if the Cloud selector cannot return valid JSON."""
    terms = [x.lower() for x in re.findall(r'[A-Za-z0-9+#./-]{2,}', str(role or ''))]
    terms += [x.lower() for t in _campaign_list(campaign.technologies)[:30] for x in re.findall(r'[A-Za-z0-9+#./-]{2,}', t)]
    best = None
    best_score = -1
    for d in docs:
        blob = (d.get('text') or '').lower()
        score = sum(min(5, blob.count(t)) for t in terms if len(t) >= 2)
        if score > best_score:
            best, best_score = d, score
    selected = best or (docs[0] if docs else None)
    role_definition = f'{role}: specialist work that directly matches the selected CV evidence and the configured campaign focus.'
    specialist = []
    if selected:
        for token in re.findall(r'(?<!\w)(?:\.?[A-Za-z][A-Za-z0-9]*(?:[+#./-][A-Za-z0-9+#.-]+)+|[A-Z][A-Z0-9]{1,9})(?!\w)', selected.get('text') or ''):
            if token.lower() not in {x.lower() for x in specialist}:
                specialist.append(token)
            if len(specialist) >= 12:
                break
    return selected, role_definition, specialist, []


def _select_cv_and_role_brief(campaign, role):
    """Use Cloud AI to select the best active CV and define the role from its actual contents.

    Selection is based on extracted CV text. Filenames/labels are intentionally not supplied to
    the model, so no role-specific filename convention or hard-coded CV mapping can influence it.
    """
    docs = extract_active_cv_texts()
    profile = Profile.objects.get_or_create(pk=1)[0]
    if not docs:
        return None, f'{role}: specialist work matching the configured role.', [], []
    cache_key = _brief_cache_key(role, docs, profile, campaign)
    scope = dict(profile.scope_json or {})
    cached = (scope.get('_cloud_role_briefs') or {}).get(cache_key) or {}
    if cached:
        selected = next((d for d in docs if str(d.get('id')) == str(cached.get('selected_cv_id'))), None)
        if selected:
            return selected, str(cached.get('role_definition') or role), list(cached.get('specialist_terms') or []), list(cached.get('title_angles') or [])

    route = cloud_discovery_route(stage='jd_analysis')
    provider, model = route.get('provider'), route.get('model')
    doc_payload = []
    for d in docs[:8]:
        # Text, not filename/label. Keep each CV bounded so the selector is cheaper than the search itself.
        doc_payload.append({'cv_id': d.get('id'), 'text': (d.get('text') or '')[:9000]})
    steering = {
        'role': str(role or '').strip(),
        'technologies': _campaign_list(campaign.technologies)[:30],
        'priority': (profile.high_priority_text or '')[:900],
    }
    prompt = f'''Choose the ONE uploaded CV whose actual content best supports this role, then define what the role should mean for web research. Do not use filenames or labels; only the CV text is evidence.

Role and steering context:
{json.dumps(steering, ensure_ascii=False)}

CVs:
{json.dumps(doc_payload, ensure_ascii=False)}

Return JSON only with selected_cv_id, role_definition (1-3 precise sentences), specialist_terms (up to 15 concrete technologies/domains from that CV relevant to this role), and title_angles (up to 12 plausible titles or ways this work may be advertised). Do not dump unrelated CV skills.''' 
    try:
        with scoped_usage_context(bundle_anchor='jd_analysis', bundled_activities=['CV selection', 'role definition']):
            raw = generate_with_route(route, prompt, stage='jd_analysis', timeout=120,
                                subject={'type': 'campaign', 'id': str(campaign.pk), 'label': campaign.name, 'budget_operation': 'campaign'},
                                limits_override={'max_input_tokens': 22000, 'max_output_tokens': 1200})
        data = _extract_json(raw)
        selected = next((d for d in docs if str(d.get('id')) == str(data.get('selected_cv_id'))), None)
        if not selected:
            raise ValueError('Cloud CV selector did not identify an active CV')
        role_definition = str(data.get('role_definition') or '').strip()[:1600] or f'{role}: specialist work matching the selected CV.'
        specialist = [str(x).strip() for x in (data.get('specialist_terms') or []) if str(x).strip()][:15]
        titles = [str(x).strip() for x in (data.get('title_angles') or []) if str(x).strip()][:12]
    except Exception:
        selected, role_definition, specialist, titles = _fallback_cv_selection(role, docs, campaign)

    cache = dict(scope.get('_cloud_role_briefs') or {})
    cache[cache_key] = {
        'selected_cv_id': selected.get('id') if selected else None,
        'role_definition': role_definition,
        'specialist_terms': specialist,
        'title_angles': titles,
        'updated_at': timezone.now().isoformat(),
    }
    # Bound cache growth.
    if len(cache) > 30:
        cache = dict(list(cache.items())[-30:])
    scope['_cloud_role_briefs'] = cache
    profile.scope_json = scope
    profile.save(update_fields=['scope_json', 'updated_at'])
    return selected, role_definition, specialist, titles


def _clean_results(text, metadata, limit=30, allow_generic=False):
    data = _extract_json(text)
    rows = data.get('results') or data.get('opportunities') or []
    if not isinstance(rows, list):
        rows = []
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get('exact_url') or row.get('url') or row.get('link') or '').strip()
        title = str(row.get('title') or row.get('role') or row.get('need') or 'Cloud-discovered opportunity')[:500]
        company = str(row.get('company') or row.get('organization') or '')[:300]
        if not url.startswith(('http://', 'https://')) or is_search_engine_url(url) or is_disallowed_adult_url(url) or is_blacklisted_url(url, scope='opportunities', company=company):
            continue
        if not allow_generic and is_generic_opportunity_collection_url(url):
            continue
        key = (url, title.casefold(), company.casefold()) if allow_generic else url.casefold()
        if key in seen:
            continue
        seen.add(key)
        remote_status = str(row.get('remote_status') or 'unknown').strip().lower()
        if remote_status not in {'fully_remote', 'remote', 'hybrid', 'onsite', 'unknown'}:
            remote_status = 'unknown'
        try:
            age_days = int(row.get('age_days')) if row.get('age_days') is not None else None
        except Exception:
            age_days = None
        disposition = str(row.get('disposition') or row.get('kind') or 'opportunity_candidate').strip().lower()
        if disposition in {'lead', 'interesting', 'interesting_non_match', 'possible_contact'}:
            disposition = 'hidden_lead'
        if disposition not in {'opportunity', 'opportunity_candidate', 'hidden_lead', 'discard'}:
            disposition = 'opportunity_candidate'
        out.append({
            'candidate_id': str(row.get('candidate_id') or '')[:80],
            'title': title, 'company': company, 'url': url,
            'snippet': str(row.get('summary') or row.get('why') or row.get('evidence') or '')[:5000],
            'highlight': str(row.get('highlight') or row.get('list_highlight') or '')[:600],
            'evidence': str(row.get('evidence') or row.get('why') or row.get('summary') or '')[:10000],
            'remote_text': str(row.get('remote_text') or row.get('remote') or '')[:800],
            'remote_status': remote_status,
            'remote_confidence': _int(row.get('remote_confidence') if row.get('remote_confidence') is not None else row.get('confidence'), 0),
            'remote_reason': str(row.get('remote_reason') or '')[:1600],
            'country': _clean_company_country(row.get('company_country') or row.get('country') or row.get('location')),
            'engagement_type': str(row.get('engagement_type') or row.get('employment_type') or '')[:160],
            'company_size': str(row.get('company_size') or '')[:160],
            'application_process': str(row.get('hiring_process') or row.get('application_process') or '')[:3000],
            'application_process_role_specific': _bool(row.get('application_process_role_specific') if row.get('application_process_role_specific') is not None else True),
            'hiring_process_confidence': str(row.get('hiring_process_confidence') or '')[:30],
            'salary': str(row.get('salary') or row.get('advertised_salary') or '')[:800],
            'salary_estimate': str(row.get('salary_estimate') or row.get('credible_salary_range') or '')[:800],
            'role_feedback': str(row.get('role_feedback') or row.get('interview_feedback') or '')[:2000],
            'role_info_provenance': str(row.get('role_info_provenance') or 'role-specific')[:80],
            'role_info_confidence': str(row.get('role_info_confidence') or '')[:30],
            'founded_year': str(row.get('founded_year') or '')[:16],
            'founded_by': str(row.get('founded_by') or '')[:500],
            'posted_date': str(row.get('posted_date') or row.get('date_posted') or '')[:80],
            'posted_date_explicit': _bool(row.get('posted_date_explicit')),
            'post_age_reason': str(row.get('post_age_reason') or '')[:1800],
            'post_age_method': str(row.get('post_age_method') or '')[:80],
            'post_age_evidence': row.get('post_age_evidence') if isinstance(row.get('post_age_evidence'), list) else [],
            'age_days': max(0, age_days) if age_days is not None else None,
            'current_status': str(row.get('current_status') or row.get('status') or '')[:160],
            'recommendation': str(row.get('recommendation') or '')[:80],
            'post_age_class': str(row.get('post_age_class') or '')[:40],
            'evergreen_confidence': _int(row.get('evergreen_confidence'), 0),
            'evergreen_reason': str(row.get('evergreen_reason') or '')[:1200],
            'confidence': _int(row.get('confidence'), 0),
            '_pre_score': _int(row.get('fit_score') if row.get('fit_score') is not None else row.get('score'), 55),
            'fit_reason': str(row.get('fit_reason') or row.get('why_fit') or '')[:2000],
            'sources': _sources(row, metadata),
            'disposition': disposition,
            'lead_reason': str(row.get('lead_reason') or '')[:1800],
            'cloud_discovery': True, 'cloud_provider': metadata.get('provider', ''), 'cloud_model': metadata.get('model', ''),
        })
        if len(out) >= limit:
            break
    return out


def _extract_emails(text, html=''):
    out = []
    for source in (text or '', html or ''):
        for raw in _EMAIL_RE.findall(source):
            email = raw.strip('.,;:<>[]()').lower()
            if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                continue
            if email not in out:
                out.append(email)
            if len(out) >= 20:
                return out
    return out


def _inspect_cloud_urls(rows):
    """Directly read every Cloud-returned URL; never calls a search engine or archive API."""
    contacts = []
    for row in rows:
        url = str(row.get('url') or '').strip()
        if not url:
            continue
        try:
            inspected = fetch_target(url, row.get('title', ''), '', timeout=15)
        except Exception as exc:
            row['_inspection_error'] = str(exc)[:500]
            continue
        target = unwrap_search_result_url(str(inspected.get('target_url') or url).strip())
        if target.startswith(('http://', 'https://')):
            row['_inspected_url'] = target
        row['_page_title'] = str(inspected.get('title') or '')[:500]
        row['_page_text'] = str(inspected.get('text') or '')[:14000]
        row['_page_html'] = str(inspected.get('html') or '')[:30000]
        row['_page_ok'] = bool(inspected.get('ok'))
        row['_http_status'] = inspected.get('http_status')
        row['_checked_at'] = timezone.now().isoformat()
        row['_check_error'] = str(inspected.get('error') or '')[:500]
        emails = _extract_emails(row['_page_text'], row['_page_html'])
        row['_emails'] = emails
        for email in emails:
            contacts.append({'email': email, 'company': row.get('company', ''), 'source_url': target or url, 'title': row.get('title', '')})
    # deterministic dedupe
    dedup = {}
    for item in contacts:
        dedup[item['email']] = item
    return list(dedup.values())


def _discovery_preferences_text(profile, campaign):
    prefs = _soft_preferences(profile, campaign)
    loc = ', '.join(prefs['locations']) or 'the saved operating locations'
    bits = [f'Candidate operating locations ({loc}) are soft suitability/ranking preferences only. Do not use them to suppress discovery in other enabled markets. Clearly state explicit role geography/remote restrictions so ScoutBox can rank suitability later.']
    if prefs['company_sizes']:
        bits.append('Prefer ' + ', '.join(prefs['company_sizes'][:6]) + ' organizations when choices are otherwise comparable.')
    if prefs['engagement']:
        bits.append('Useful engagement types include ' + ', '.join(prefs['engagement'][:8]) + '.')
    if prefs['exclude_marketplaces']:
        bits.append('Avoid low-value gig marketplaces.')
    return ' '.join(bits)



def _relevant_cv_excerpt(text, role_definition, specialist_terms, title_angles, limit=7500):
    """Select role-relevant CV text without filename rules or role-specific hard-coding."""
    raw=str(text or '').strip()
    if len(raw) <= limit:
        return raw
    signals=[]
    for value in [role_definition, *(specialist_terms or []), *(title_angles or [])]:
        for token in re.findall(r'[A-Za-z0-9+#.\/-]{3,}', str(value or '').lower()):
            if token not in {'with','from','this','that','role','work','engineer','engineering','technical','remote'} and token not in signals:
                signals.append(token)
    # CV extractors usually preserve paragraph/newline structure. Score compact blocks by the
    # AI-inferred role evidence, then preserve original order for readable context.
    blocks=[b.strip() for b in re.split(r'\n\s*\n|(?<=\.)\s+(?=[A-Z][A-Za-z ]{2,40}:)', raw) if b.strip()]
    if len(blocks)<4:
        blocks=[b.strip() for b in raw.splitlines() if b.strip()]
    ranked=[]
    for i,b in enumerate(blocks):
        low=b.lower(); score=sum(2 if len(sig)>5 else 1 for sig in signals if sig in low)
        # Keep concise profile/skills headings as useful context when present; this is structural,
        # not a filename or role rule.
        if i<3: score+=1
        ranked.append((score,i,b))
    selected=[]; used=0
    for score,i,b in sorted(ranked,key=lambda x:(-x[0],x[1])):
        if score<=0 and selected: continue
        piece=b[:2200]
        if used+len(piece)+2>limit: continue
        selected.append((i,piece)); used+=len(piece)+2
        if used>=limit*0.85: break
    if not selected:
        return raw[:limit]
    return '\n\n'.join(b for _,b in sorted(selected))[:limit]

def _custom_domain_url(value):
    raw=str(value or '').strip()
    if not raw:
        return ''
    if not raw.startswith(('http://','https://')):
        raw='https://'+raw
    return raw


def _research_custom_domain(campaign, domain_obj, role_brief, search_budget=4, test=False):
    """Research one enabled Custom Domain with Cloud-native search, then direct retrieval fallback."""
    target=_custom_domain_url(domain_obj.domain)
    if not target:
        return [], '', {}, 'invalid'
    definition=str((role_brief or {}).get('definition') or 'specialist technical work')
    specialist=', '.join((role_brief or {}).get('specialist_terms') or [])
    prompt=(
        'Research this configured ScoutBox Custom Domain as an explicit discovery target: '+target+'\n'
        'Find new/recent relevant remote job posts, consulting/project opportunities, hiring signals or actionable lead material matching: '+definition+'. '
        'Relevant specialist evidence: '+specialist+'. Prefer exact item URLs and prefer a direct employer/company listing over a third-party copy when both exist. '
        'Do not invent URLs or facts. Return JSON only as {"results":[...]} using ScoutBox candidate fields: url, title, company, summary, remote_text, remote_status, confidence, sources, disposition, lead_reason.'
    )
    text=''; meta={}
    try:
        with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['Cloud native custom-domain research'], custom_domain=target):
            text,meta=cloud_web_search(prompt,timeout=100 if test else 180,stage='url_scrape')
        rows=_clean_results(text,meta,limit=10,allow_generic=True)
        UsageMetric.objects.create(category='cloud_custom_domain',provider=str(meta.get('provider') or ''),stage='cloud_native_domain_research',requests=1,metadata={'domain':target,'results':len(rows),'route':'cloud_native'})
        if rows:
            return rows,text,meta,'cloud_native'
    except Exception as exc:
        meta={'error':str(exc)}
    try:
        inspected=fetch_target(target, str(domain_obj.name or domain_obj.domain), '', timeout=15)
        page_text=str(inspected.get('text') or inspected.get('clean_text') or '')[:30000]
        if not page_text:
            raise RuntimeError(inspected.get('error') or 'No usable page text returned')
        route=cloud_discovery_route(stage='url_scrape'); provider,model=route.get('provider'),route.get('model')
        if not provider or provider=='ollama' or not model:
            raise RuntimeError('No configured Cloud AI model is available for Custom Domain fallback')
        fallback=(
            'ScoutBox directly retrieved this configured Custom Domain because Cloud-native domain research did not return useful material. '
            'Analyze only the supplied page content and identify relevant current jobs/opportunities/leads matching '+definition+'. '
            'Prefer exact direct-company URLs present in the supplied page. Never invent a URL. Return JSON only as {"results":[...]}.\n\n'
            'DOMAIN: '+target+'\n\nPAGE CONTENT:\n'+page_text
        )
        with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['Direct custom-domain retrieval','Cloud analysis'], custom_domain=target):
            out=generate_with_route(route,fallback,stage='url_scrape',timeout=150,subject={'type':'custom_domain','id':str(domain_obj.pk),'label':domain_obj.name or domain_obj.domain,'budget_operation':'page_recovery'})
        fmeta={'provider':provider,'model':model,'sources':[target]}
        rows=_clean_results(out,fmeta,limit=10,allow_generic=True)
        UsageMetric.objects.create(category='cloud_custom_domain',provider=str(provider or ''),stage='direct_domain_retrieval_cloud_analysis',requests=1,pages=1,bytes_downloaded=int(inspected.get('bytes') or 0),metadata={'domain':target,'results':len(rows),'route':'direct_retrieval_cloud_analysis'})
        return rows,out,fmeta,'direct_retrieval_cloud_analysis'
    except Exception as exc:
        UsageMetric.objects.create(category='cloud_custom_domain',provider='',stage='custom_domain_failed',requests=1,errors=1,metadata={'domain':target,'error':str(exc)[:500]})
        return [],text,meta,'failed'


def _research_role(campaign, role, selected_cv, role_definition, specialist_terms, title_angles, max_rows, search_budget, custom_block='', test=False):
    profile = Profile.objects.get_or_create(pk=1)[0]
    cv_text = _relevant_cv_excerpt((selected_cv or {}).get('text', ''), role_definition, specialist_terms, title_angles, limit=7500)
    prefs = _discovery_preferences_text(profile, campaign)
    angles = ', '.join(title_angles[:10]) if title_angles else 'infer related titles from the work itself'
    prompt = f'''Find current remote work matching this role using live web research.

Role: {role_definition}
Useful related titles: {angles}.
{prefs}

Search naturally across direct employer postings, contracts, specialist consultancies, small technical companies, open-source/community hiring signals, and adjacent titles that describe the same work. If a role is first found on a third-party listing/aggregator, actively look for the same exact role on the employer's own website and prefer that verified direct-company item URL. Never replace an exact posting with a generic careers page. Do not spend result slots on obviously on-site or geographically ineligible jobs. Use up to {max(3, int(search_budget))} focused web searches if useful.

If you find a few organizations or projects with no suitable open role but that appear genuinely worth contacting directly about this kind of work, include them as possible contacts. Do not include ordinary rejected jobs, career pages, blogs, job boards, directories, documentation sites, or generic resources.

Current admission policy: {selectivity_instruction('opportunities')} {selectivity_instruction('hidden_leads')}

Relevant excerpt from the selected CV (supporting evidence, not a keyword checklist):
{cv_text}{custom_block}

Return JSON only: {{"results":[...]}} with at most {max_rows} concise rows. Each row: url, title, company, summary (1-2 sentences), remote_text, remote_status (fully_remote/remote/unknown), confidence (0-100), sources, disposition (opportunity_candidate or possible_contact), lead_reason. A generic careers/ATS page may be discovery evidence for a named role, but it is never itself a final Opportunity or possible contact. Never invent a URL or fact.'''
    with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['URL discovery', 'role-specific research'], primary_role=role):
        text, meta = cloud_web_search(prompt, timeout=100 if test else 210, stage='url_scrape')
    parsed = _extract_json(text)
    structured = isinstance(parsed.get('results') or parsed.get('opportunities'), list)
    if not structured or _provider_response_truncated(meta):
        # Initial discovery can be truncated too. Retry once with a deliberately smaller
        # concise result set; an invalid second response is a provider-processing failure,
        # not a legitimate zero-match campaign.
        retry_rows = max(4, min(8, int(max_rows)))
        retry_prompt = prompt + f'\n\nYour previous response was incomplete or not valid JSON. Retry with at most {retry_rows} of the strongest candidates, keep every summary to one short sentence, and return one complete JSON object.'
        with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['URL discovery retry', 'truncated JSON recovery'], primary_role=role):
            retry_text, retry_meta = cloud_web_search(retry_prompt, timeout=120 if test else 210, stage='url_scrape')
        retry_parsed = _extract_json(retry_text)
        retry_structured = isinstance(retry_parsed.get('results') or retry_parsed.get('opportunities'), list)
        if not retry_structured:
            raise RuntimeError('Cloud discovery returned incomplete or malformed structured JSON after a compact retry.')
        text, meta, prompt = retry_text, retry_meta, retry_prompt
        max_rows = retry_rows
    return _clean_results(text, meta, limit=max_rows, allow_generic=True), text, meta, prompt


def _resolver_prompt(role_definition, specialist_terms, profile, campaign, compact, search_budget, custom_block=''):
    prefs = _discovery_preferences_text(profile, campaign)
    return f'''Verify these {len(compact)} candidate(s) using focused live web research before ScoutBox stores anything.

Target work: {role_definition}
Relevant fit evidence: {', '.join(specialist_terms[:12])}.
{prefs}
Current admission policy: {selectivity_instruction('opportunities')} {selectivity_instruction('hidden_leads')}
Pay threshold, company size, and engagement type are SOFT ranking preferences only. Missing or mismatched values must not reject an otherwise relevant remote opportunity.

For each candidate: resolve the exact item-level role/project URL; when a third-party/aggregator copy is supplied, search for and prefer the verified exact employer-hosted posting if it exists (keep the third-party URL only as provenance; never substitute a generic careers page); verify the work itself is remote and workable from the saved operating location; confirm it still appears open/current; rank technical fit; estimate posting age; and identify the employer/company's actual HQ or primary operating country. When public evidence conveniently supports it, also capture advertised/credible salary context, role-specific interview/application feedback, and the hiring process (screening, assessments, interview rounds, take-home/panel/final stages or typical timing). Label company-general hiring information as such and never present it as definitely role-specific. Also capture founding year/founder only when credible public evidence is present; leave unknown fields blank rather than guessing. The country field is COMPANY LOCATION only; never put Remote, Remote worldwide, Anywhere, Home based, or similar work-arrangement text there.

For posting age, use the employer/ATS page and public corroboration. If useful, you MAY use ordinary Cloud web research to find archive.org evidence, but do not assume an archive date is the posting date and do not use or request any archive.org API. Return posted_date_explicit=true only when the specific item itself states the date. If no explicit date exists, make a cautious best estimate when evidence supports one, mark post_age_method="inferred" or "guess", give post_age_reason, and lower confidence rather than returning a fabricated precise fact. Also classify post_age_class as "evergreen" only when the role appears to be a long-running, rolling, standing, repeatedly reposted, or continuously open vacancy based on employer/cache/index/aggregator/archive evidence while still accepting applications. Evergreen does NOT mean closed or ineligible. Otherwise use "normal" or "unknown". Give evergreen_confidence and evergreen_reason.

A generic careers/ATS board cannot be an Opportunity. If no exact URL can be established, you may instead identify an organization that appears genuinely worth a direct approach about this work, but ordinary rejected jobs, career pages, blogs, job boards and generic resources are not such contacts. ScoutBox will run a separate actionability check before storing one. Hybrid/on-site/incompatible region-only jobs are not Opportunities.

Use up to {max(2, int(search_budget))} searches for this small batch. Never invent facts.{custom_block}

Candidates and directly inspected page evidence:
{json.dumps(compact, ensure_ascii=False)}

Return JSON only: {{"results":[...]}}. Preserve candidate_id. Each row: candidate_id, exact_url, title, company, summary, highlight, evidence, remote_text, remote_status (fully_remote/remote/hybrid/onsite/unknown), remote_confidence (0-100), remote_reason, country (for an opportunity: actual job/work-location country when explicit; for a possible_contact: company/HQ country), engagement_type, company_size, founded_year, founded_by, salary, salary_estimate, role_feedback, role_info_provenance (role-specific/company-general), role_info_confidence (High/Medium/Low), application_process, application_process_role_specific, hiring_process_confidence (High/Medium/Low), posted_date, posted_date_explicit, post_age_method (explicit/inferred/guess/unknown), post_age_class (normal/evergreen/unknown), evergreen_confidence (0-100), evergreen_reason, post_age_reason, post_age_evidence (up to 5 objects with source/date/url/reason/confidence), age_days, current_status, fit_score (0-100), fit_reason, recommendation (Apply Now/Review/Information Only), confidence (0-100), sources, disposition (opportunity/possible_contact/discard), lead_reason. For every disposition=opportunity row, highlight is REQUIRED and must be a concise technical summary grounded in the actual role/JD. Prefer about 25-40 words and never exceed 50 words. Summarize the concrete technologies, subsystems, architectures, protocols, specialist responsibilities and work area that distinguish the role. Do not add generic candidate-fit commentary. Do NOT write recommendation prose such as "highly relevant", "actionable", "strong match", "clear opportunity", "aligns with the candidate", or "job posting provides". If fit is adjacent or weak, say so plainly. Do not end with a generic label such as "fit", "good fit", or "technical fit"; state the concrete reason instead. Avoid em dashes; use a short sentence fragment, colon, comma, or semicolon when punctuation is needed. Never infer highlight from search-query wording, related-job widgets, or unrelated page text; do not copy a long JD passage or repeat the company. Hidden-lead/discard rows may leave highlight blank. For post age, a page/item updated/modified date or HTTP Last-Modified is not a posting date: never use it as posted_date or to calculate age_days; if that is the only date evidence, return posted_date=null, age_days=null and post_age_method=unknown. Relative posting phrases such as "4 months ago" are valid evidence when clearly attached to this role. Recommendation describes usefulness/action priority; pay, company size and engagement type remain soft ranking preferences and must not force Information Only by themselves.'''


def _resolve_batch(batch, role_definition, specialist_terms, profile, campaign, search_budget, custom_block=''):
    compact = []
    for row in batch:
        compact.append({
            'candidate_id': row['candidate_id'], 'url': row.get('url'), 'title': row.get('title'), 'company': row.get('company'),
            'summary': row.get('snippet'), 'remote_text': row.get('remote_text'), 'remote_status': row.get('remote_status'),
            'page_url': row.get('_inspected_url') or row.get('url'), 'page_title': row.get('_page_title'),
            'page_excerpt': (row.get('_page_text') or '')[:7000],
        })
    prompt = _resolver_prompt(role_definition, specialist_terms, profile, campaign, compact, max(2, min(search_budget, len(batch) * 4)), custom_block)
    with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['exact URL resolution', 'remote verification', 'post-age research', 'fit ranking'], verification_pass=True):
        text, meta = cloud_web_search(prompt, timeout=240, stage='jd_analysis')
    data = _extract_json(text)
    results = data.get('results') or []
    if not isinstance(results, list):
        results = []
    valid = [x for x in results if isinstance(x, dict) and str(x.get('candidate_id') or '')]
    return valid, text, meta, prompt


def _resolve_candidates(rows, role_definition, specialist_terms, profile, campaign, search_budget, custom_block=''):
    """Resolve in batches of four and retry malformed/truncated JSON one candidate at a time."""
    if not rows:
        return [], [], '', {}, 0
    for i, row in enumerate(rows, 1):
        row['candidate_id'] = f'c{i}'
    verified_by_id, texts, metas, retries = {}, [], [], 0
    for start in range(0, len(rows), 4):
        batch = rows[start:start + 4]
        try:
            verified, text, meta, _ = _resolve_batch(batch, role_definition, specialist_terms, profile, campaign, search_budget, custom_block)
        except Exception:
            verified, text, meta = [], '', {}
        texts.append(text); metas.append(meta)
        for v in verified:
            verified_by_id[str(v.get('candidate_id'))] = v
        missing = [r for r in batch if r['candidate_id'] not in verified_by_id]
        # Invalid JSON or a truncated second object must not erase the first candidate.
        for row in missing:
            retries += 1
            try:
                one, text2, meta2, _ = _resolve_batch([row], role_definition, specialist_terms, profile, campaign, max(2, search_budget), custom_block)
            except Exception:
                one, text2, meta2 = [], '', {}
            texts.append(text2); metas.append(meta2)
            for v in one:
                verified_by_id[str(v.get('candidate_id'))] = v

    opportunities, hidden = [], []
    for original in rows:
        v = verified_by_id.get(original['candidate_id'])
        if not v:
            # Preserve a Cloud-declared interesting non-match instead of silently deleting it.
            if original.get('disposition') == 'hidden_lead' and original.get('company'):
                hidden.append({**original, 'lead_reason': original.get('lead_reason') or original.get('snippet') or 'Cloud research marked this organization/project as worth exploring.'})
            continue
        merged = dict(original)
        for key, value in v.items():
            if value not in (None, ''):
                merged[key if key != 'exact_url' else 'url'] = value
        merged['candidate_id'] = original['candidate_id']
        merged['remote_confidence'] = _int(v.get('remote_confidence'), original.get('remote_confidence', 0))
        merged['confidence'] = _int(v.get('confidence'), original.get('confidence', 0))
        merged['_pre_score'] = _int(v.get('fit_score'), original.get('_pre_score', 55))
        merged['posted_date_explicit'] = _bool(v.get('posted_date_explicit'))
        merged['country'] = _clean_company_country(v.get('country') or merged.get('country'))
        merged['recommendation'] = str(v.get('recommendation') or merged.get('recommendation') or '')[:80]
        merged['post_age_class'] = str(v.get('post_age_class') or merged.get('post_age_class') or '')[:40].lower()
        merged['evergreen_confidence'] = _int(v.get('evergreen_confidence'), merged.get('evergreen_confidence', 0))
        merged['evergreen_reason'] = str(v.get('evergreen_reason') or merged.get('evergreen_reason') or '')[:1200]
        if isinstance(v.get('post_age_evidence'), list):
            merged['post_age_evidence'] = v.get('post_age_evidence')[:5]
        try:
            merged['age_days'] = max(0, int(v.get('age_days'))) if v.get('age_days') is not None else original.get('age_days')
        except Exception:
            pass
        disposition = str(v.get('disposition') or '').strip().lower()
        if disposition == 'possible_contact':
            disposition = 'hidden_lead'
        status = str(merged.get('remote_status') or 'unknown').lower()
        current = str(merged.get('current_status') or '').strip().lower()
        exact_ok = looks_like_specific_opportunity_url(merged.get('url')) and not is_generic_opportunity_collection_url(merged.get('url')) and not is_blacklisted_url(merged.get('url'), scope='opportunities', company=merged.get('company'))
        remote_ok = status in REMOTE_ACCEPTED and int(merged.get('remote_confidence') or 0) >= 55
        current_ok = current not in {'closed', 'expired', 'filled', 'removed', 'inactive', 'reject', 'reject_generic_url'}
        opp_level=selectivity_current('opportunities'); opp_rules=opportunity_thresholds(opp_level)
        selectivity_ok=(int(merged.get('confidence') or 0)>=int(opp_rules['confidence']) and int(merged.get('_pre_score') or 0)>=int(opp_rules.get('fit_score') or 0))
        selectivity_hits=[]
        if selectivity_ok and opp_rules.get('requires_campaign_anchor'):
            selectivity_ok,selectivity_hits=campaign_alignment(campaign,merged.get('title') or '', ' '.join(str(merged.get(k) or '') for k in ('summary','highlight','evidence','fit_reason','_page_text')), level=opp_level,kind='opportunity')
        merged['_opportunity_selectivity']={'level':opp_level,'campaign_hits':selectivity_hits,'policy':opp_rules}
        if disposition == 'opportunity' and exact_ok and remote_ok and current_ok and selectivity_ok:
            opportunities.append(merged)
        elif disposition == 'hidden_lead' and merged.get('company'):
            merged['lead_reason'] = str(v.get('lead_reason') or merged.get('lead_reason') or merged.get('evidence') or '')[:1800]
            hidden.append(merged)
        elif exact_ok and remote_ok and current_ok and selectivity_ok and disposition not in {'discard', 'hidden_lead'}:
            opportunities.append(merged)

    def dedupe(rows, key_fn):
        out, seen = [], set()
        for row in rows:
            key = key_fn(row)
            if not key or key in seen:
                continue
            seen.add(key); out.append(row)
        return out
    opportunities = dedupe(opportunities, lambda r: str(r.get('url') or '').strip().casefold())
    hidden = dedupe(hidden, lambda r: (str(r.get('company') or '').strip().casefold(), str(r.get('url') or '').strip().casefold()))
    meta = dict(next((m for m in reversed(metas) if m), {}) or {})
    meta['_verified_count']=len(verified_by_id)
    meta['_input_count']=len(rows)
    meta['_unresolved_count']=max(0,len(rows)-len(verified_by_id))
    return opportunities, hidden, '\n\n--- verification pass ---\n'.join(x for x in texts if x), meta, retries


def _remaining_deep_capacity(cfg):
    run_id = usage_context().get('campaign_run_id')
    limit = max(0, int(cfg.cloud_deep_research_candidates_per_run or 0))
    if not run_id or limit <= 0:
        return limit or 9999
    used = CloudRunUsage.objects.filter(campaign_run_id=run_id).values_list('deep_research_candidates', flat=True).first() or 0
    return max(0, limit - int(used))


def _lead_noise_url(url):
    """Cheap pre-check; a surviving candidate still needs Cloud actionability qualification."""
    raw = str(url or '').strip()
    if not raw or is_disallowed_adult_url(raw):
        return True
    try:
        p = urlsplit(raw)
        host = p.netloc.lower().removeprefix('www.')
        path = (p.path or '/').lower().rstrip('/')
    except Exception:
        return True
    if is_blacklisted_url(raw, scope='hidden_leads', company=company):
        return True
    if any(x in host for x in ('workable.com','greenhouse.io','ashbyhq.com','lever.co','smartrecruiters.com','workdayjobs.com','myworkdayjobs.com')):
        return True
    if re.search(r'/(?:blog|blogs|article|articles|news|press|docs|documentation|tutorials?|resources?)(?:/|$)', path):
        return True
    return False


def _lead_final_url_invalid(url):
    """A stored lead must be a direct company/contact target, never a careers page."""
    raw = str(url or '').strip()
    if _lead_noise_url(raw):
        return True
    try:
        path = (urlsplit(raw).path or '/').lower().rstrip('/')
    except Exception:
        return True
    if re.search(r'/(?:careers?|jobs?|vacancies|openings|positions|join-us|work-with-us)(?:\.html?)?$', path):
        return True
    if re.search(r'/(?:careers?|jobs?|vacancies|openings|positions)(?:/|$)', path):
        return True
    return False


def _qualify_hidden_leads(campaign, rows, role_briefs, search_budget, custom_block=''):
    """Cloud-only second pass: persist only directly actionable outreach targets."""
    candidates = []
    seen = set()
    for i, row in enumerate(rows or [], 1):
        company = str(row.get('company') or '').strip()
        url = str(row.get('_inspected_url') or row.get('url') or '').strip()
        if not company or not url:
            continue
        key = (company.casefold(), url.casefold())
        if key in seen:
            continue
        seen.add(key)
        # Obvious content/ATS targets cannot themselves be leads. A later Cloud decision
        # may replace a non-noise company URL with a better direct-contact URL.
        if _lead_noise_url(url):
            continue
        item = dict(row)
        item['_lead_candidate_id'] = f'l{i}'
        candidates.append(item)
    if not candidates:
        return [], {'candidates': len(rows or []), 'qualified': 0, 'rejected': len(rows or []), 'requests': 0}

    qualified = []
    requests = 0
    for start in range(0, len(candidates), 3):
        batch = candidates[start:start + 3]
        compact = []
        for row in batch:
            idx = int(row.get('_role_index') or 0)
            rb = role_briefs[idx] if role_briefs and 0 <= idx < len(role_briefs) else (role_briefs[0] if role_briefs else {})
            compact.append({
                'candidate_id': row['_lead_candidate_id'],
                'company': row.get('company'),
                'url': row.get('_inspected_url') or row.get('url'),
                'title_or_need': row.get('title'),
                'why_it_was_nominated': row.get('lead_reason') or row.get('snippet') or row.get('evidence'),
                'role_context': str(rb.get('definition') or '')[:1000],
                'page_title': row.get('_page_title'),
                'page_excerpt': str(row.get('_page_text') or '')[:6500],
                'public_email_candidates': list(row.get('_emails') or [])[:12],
                'known_company_size': str(row.get('company_size') or '')[:300],
                'known_founded_year': str(row.get('founded_year') or '')[:40],
                'known_founded_by': str(row.get('founded_by') or '')[:500],
                'known_sources': list(row.get('sources') or [])[:12],
            })
        prompt = f"""Decide whether each item is genuinely worth a direct work-related approach.

Technical relevance alone is not enough. Keep it only when the candidate can make a tailored direct approach now (email, contact form, consultancy enquiry, collaboration or contractor intake) with a realistic chance of reaching a relevant human. Think 'worth contacting directly', not 'interesting web page'.

Reject blogs/articles/news/docs/tutorials/resources, generic job boards or ATS vendors, directories, broad communities/foundations/training portals without a specific relevant intake/contact route, expired-job remnants, and organizations for which the only evidence is general technical relevance. Workable/Greenhouse/Ashby/etc. are infrastructure, never the lead themselves. A specialist company may qualify even when it was discovered through a careers page, but the returned target_url MUST be a normal company/contact/consulting/collaboration page, never careers/jobs/vacancies/ATS.

For a kept lead, return the organization's actual headquarters or primary operating country when it can be supported; otherwise leave country blank. Never use Remote, Remote worldwide, Anywhere, Global, Home based, or Distributed as company location. Also preserve or verify compact Company Info while you are already researching the lead: return company_size as a public employee count/range when supported, founded_year as a 4-digit year when supported, and founded_by when supported. Prefer the organization's own site or another credible public source; leave unknown fields blank rather than guessing. Return company_info_sources as URLs that specifically support those company facts when available. This is enrichment of Hidden Leads only and must not change opportunity eligibility. Return a concise reason. For contact_path, return only concrete contact data that adds to target_url, such as a public email address or a DIFFERENT direct contact-form/contact URL. Do not return generic outreach advice, templates, or phrases like 'reach out via their website'. Leave contact_path blank when it contains no new concrete email or distinct URL. Use live web research when useful. Never invent a contact path.{custom_block}

Candidates:
{json.dumps(compact, ensure_ascii=False)}

Return JSON only: {{"results":[...]}}. Each row: candidate_id, qualify (true/false), company, target_url, country, company_size, founded_year, founded_by, company_info_sources, lead_reason, contact_path, confidence (0-100)."""
        try:
            with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['Hidden Lead qualification', 'direct-contact actionability']):
                text, _meta = cloud_web_search(prompt, timeout=180, stage='cold_contact')
            requests += 1
            data = _extract_json(text)
            decisions = data.get('results') or []
        except Exception:
            decisions = []
        byid = {str(x.get('candidate_id')): x for x in decisions if isinstance(x, dict) and x.get('candidate_id')}
        for row in batch:
            d = byid.get(row['_lead_candidate_id']) or {}
            keep = _bool(d.get('qualify')) and _int(d.get('confidence'), 0) >= 60
            target = str(d.get('target_url') or row.get('_inspected_url') or row.get('url') or '').strip()
            if keep and target.startswith(('http://', 'https://')) and not _lead_final_url_invalid(target):
                merged = dict(row)
                merged['url'] = target
                merged['company'] = str(d.get('company') or row.get('company') or '')[:300]
                merged['country'] = _clean_company_country(d.get('country') or row.get('country'))
                merged['lead_reason'] = str(d.get('lead_reason') or row.get('lead_reason') or '')[:1800]
                # Hidden Lead qualification is already a live-web research pass. Reuse that
                # same response for compact Company Info rather than waiting for a separate
                # Company Research request after the lead appears in the list.
                merged['company_size'] = str(d.get('company_size') or row.get('company_size') or '')[:300]
                merged['founded_year'] = str(d.get('founded_year') or row.get('founded_year') or '')[:40]
                merged['founded_by'] = str(d.get('founded_by') or row.get('founded_by') or '')[:500]
                extra_sources = d.get('company_info_sources') or []
                if isinstance(extra_sources, str):
                    extra_sources = [extra_sources]
                sources = list(row.get('sources') or [])
                for source_url in extra_sources:
                    source_url = str((source_url.get('url') if isinstance(source_url, dict) else source_url) or '').strip()
                    if source_url.startswith(('http://', 'https://')) and source_url not in sources:
                        sources.append(source_url)
                merged['sources'] = sources[:40]
                merged['_contact_path'] = str(d.get('contact_path') or '')[:1200]
                merged['_lead_qualification_confidence'] = _int(d.get('confidence'), 0)
                qualified.append(merged)
    return qualified, {
        'candidates': len(rows or []),
        'qualified': len(qualified),
        'rejected': max(0, len(rows or []) - len(qualified)),
        'requests': requests,
    }


def _inspect_final_rows(rows):
    """Inspect exact/replacement URLs returned by later Cloud passes too."""
    inspected_count = 0
    for row in rows or []:
        url = str(row.get('url') or '').strip()
        if not url.startswith(('http://', 'https://')):
            continue
        already = str(row.get('_inspected_url') or '').strip()
        if already and already.rstrip('/') == url.rstrip('/') and row.get('_page_ok'):
            continue
        try:
            inspected = fetch_target(url, row.get('title', ''), '', timeout=15)
        except Exception as exc:
            row['_final_inspection_error'] = str(exc)[:500]
            continue
        target = unwrap_search_result_url(str(inspected.get('target_url') or url).strip())
        row['_inspected_url'] = target or url
        row['_page_title'] = str(inspected.get('title') or row.get('_page_title') or '')[:500]
        row['_page_text'] = str(inspected.get('text') or '')[:14000]
        row['_page_html'] = str(inspected.get('html') or '')[:30000]
        row['_page_ok'] = bool(inspected.get('ok'))
        row['_http_status'] = inspected.get('http_status')
        row['_checked_at'] = timezone.now().isoformat()
        row['_check_error'] = str(inspected.get('error') or '')[:500]
        row['_emails'] = _extract_emails(row['_page_text'], row['_page_html'])
        inspected_count += int(bool(inspected.get('ok')))
    return inspected_count


_CLOUD_CONTACT_REJECT_MARKERS = {
    'gdpr', 'privacy', 'privacyoffice', 'dataprotection', 'dpo', 'eeo', 'eeocompliance', 'compliance',
    'legal', 'legalnotice', 'abuse', 'security', 'securityteam', 'dmca', 'copyright', 'press', 'media',
    'investor', 'investors', 'investorrelations', 'noreply', 'no-reply', 'donotreply', 'mailerdaemon',
}
_CLOUD_CONTACT_GENERIC_USEFUL = {'jobs', 'job', 'careers', 'career', 'recruiting', 'recruitment', 'talent', 'hr', 'humanresources', 'people', 'applications', 'apply', 'hiring'}
_CLOUD_CONTACT_GENERIC_OK = {'hello', 'info', 'contact', 'office'}
_FREE_MAIL = {'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com', 'protonmail.com', 'proton.me', 'live.com', 'msn.com', 'aol.com', 'gmx.com'}


def _contact_local(email):
    return str(email or '').split('@', 1)[0].lower().split('+', 1)[0]


def _cloud_contact_noise(email):
    local = _contact_local(email)
    compact = re.sub(r'[^a-z0-9]+', '', local)
    for marker in _CLOUD_CONTACT_REJECT_MARKERS:
        if re.sub(r'[^a-z0-9]+', '', marker) in compact:
            return True
    return False


def _cloud_contact_name_from_email(email):
    """Practical salutation-grade name for Cloud-derived contacts only."""
    email = str(email or '').strip().lower()
    if not email or '@' not in email or _cloud_contact_noise(email):
        return ''
    local = _contact_local(email)
    compact = re.sub(r'[^a-z0-9]+', '', local)
    if compact in _CLOUD_CONTACT_GENERIC_USEFUL or compact in _CLOUD_CONTACT_GENERIC_OK:
        return ''
    parts = [p for p in re.split(r'[._-]+', local) if p]
    if len(parts) == 1:
        part = re.sub(r'\d+', '', parts[0])
        if not part or len(part) < 2 or part in {'team', 'admin', 'support', 'sales', 'billing', 'service'} or any(part.endswith(suffix) for suffix in ('jobs','careers','recruiting','recruitment','talent','support','contact')):
            return ''
        if len(part) <= 3 and part.isalpha():
            return part.upper()
        return part.capitalize()[:200]
    words = []
    for part in parts[:4]:
        part = re.sub(r'\d+', '', part)
        if not part:
            continue
        words.append(part.upper() if len(part) == 1 else part.capitalize())
    return ' '.join(words)[:200]


def _domain_company(email):
    domain = str(email or '').split('@', 1)[1].lower() if '@' in str(email or '') else ''
    if not domain or domain in _FREE_MAIL:
        return ''
    labels = [x for x in domain.split('.') if x and x not in {'www', 'mail', 'email', 'smtp'}]
    if not labels:
        return ''
    base = labels[-2] if len(labels) >= 2 else labels[0]
    return (base.replace('-', ' ').replace('_', ' ').title() + ('.' + labels[-1] if len(labels) >= 2 else ''))[:200]


def _collect_contact_candidates(rows):
    out = []
    seen = set()
    for row in rows or []:
        company = str(row.get('company') or '').strip()
        url = str(row.get('_inspected_url') or row.get('url') or '').strip()
        page_excerpt=str(row.get('_page_text') or '')[:7000]
        for email in list(row.get('_emails') or [])[:20]:
            email = str(email or '').strip().lower()
            if not email or email in seen or _cloud_contact_noise(email):
                continue
            if not assignable_contact_email(email,page_excerpt) or contact_email_has_non_contact_context(email,page_excerpt):
                continue
            seen.add(email)
            out.append({
                'email': email,
                'company': company,
                'source_url': url,
                'title': str(row.get('title') or '')[:300],
                'page_excerpt': page_excerpt,
                'target_kind': 'opportunity' if row.get('remote_status') in REMOTE_ACCEPTED and looks_like_specific_opportunity_url(row.get('url')) else 'hidden_lead',
                'company_summary': str(row.get('summary') or row.get('snippet') or row.get('lead_reason') or '')[:1200],
                'company_country': _clean_company_country(row.get('company_country') or row.get('country')),
                'company_intel': _cloud_lead_company_intel(row,company,url),
            })
    return out


def _qualify_cloud_contacts(rows, campaign):
    """Validate Cloud-scraped emails before Address Book persistence; fail closed."""
    contact_level=selectivity_current('address_book')
    candidates = _collect_contact_candidates(rows)
    if not candidates:
        return [], {'candidates': 0, 'validated': 0, 'rejected': 0, 'requests': 0}
    validated = []
    requests = 0
    for start in range(0, len(candidates), 6):
        batch = candidates[start:start + 6]
        prompt = f"""Validate these public email addresses for ScoutBox Address Book outreach. They were scraped from pages returned during CLOUD WEB discovery.

Keep an address only when it is genuinely associated with the named organization/role/lead and follows the current contact policy below. A real named/person mailbox or explicit regional route such as singapore@company.com or apac@company.com is normally preferred.

Current contact policy: {selectivity_instruction('address_book', contact_level)}

In Balanced or Verified mode, reject generic functional inboxes such as info@, contact@, hello@, sales@, support@, jobs@, careers@, recruiting@, hr@, admin@, office@, team@, help@, service@, billing@, applications@ and similar department/shared mailboxes. In Broad mode, a clearly organization-owned jobs/careers/recruiting/talent/engineering/research/partnerships/projects/consulting route may be kept as an organization contact, but it is never a person. At every level reject example/demo/test/customer addresses embedded in page copy, unrelated third-party/client addresses, and legal/privacy/GDPR/EEO/compliance, abuse, press/media, investor-relations, noreply, disability/accommodation/accessibility helpdesks or similar administrative mailboxes. If the email domain differs from the organization's website, do NOT assign it to that organization unless the page evidence explicitly proves the relationship; otherwise reject it. Do not invent a person's name.

For an address you keep, return company as the organization the mailbox actually belongs to. Return person_name only when the page/research explicitly identifies a person.

Candidates:
{json.dumps(batch, ensure_ascii=False)}

Return JSON only: {{"results":[...]}}. Each row: email, keep (true/false), company, person_name, relationship (person/recruiting/general/other), reason, confidence (0-100)."""
        try:
            with scoped_usage_context(bundle_anchor='url_scrape', bundled_activities=['Address Book contact validation', 'email ownership check']):
                text, _meta = cloud_web_search(prompt, timeout=180, stage='company_enrichment')
            requests += 1
            data = _extract_json(text)
            decisions = data.get('results') or []
        except Exception:
            decisions = []
        byemail = {str(x.get('email') or '').strip().lower(): x for x in decisions if isinstance(x, dict)}
        for item in batch:
            email = item['email']
            d = byemail.get(email) or {}
            if not (_bool(d.get('keep')) and _int(d.get('confidence'), 0) >= 60) or _cloud_contact_noise(email):
                continue
            # Domain ownership is deterministic and must win over a model's page-context guess.
            domain_company = _domain_company(email)
            researched_company = str(d.get('company') or item.get('company') or '').strip()
            # Domain ownership remains deterministic, but preserve a researched official
            # spelling when it normalizes to the same organization (Implicit Conversions
            # rather than Implicitconversions).
            def _slug_company(v): return re.sub(r'[^a-z0-9]+','',str(v or '').lower().replace('.com','').replace('.io','').replace('.ai',''))
            company = researched_company if researched_company and _slug_company(researched_company)==_slug_company(domain_company) else domain_company
            company = company or researched_company
            # Verified mode never creates identity from the mailbox local-part. Balanced
            # keeps the pre-0.11.54 salutation behavior; Broad may additionally retain
            # a useful organization route without pretending it is a person.
            explicit_name=str(d.get('person_name') or '').strip()[:200]
            name = explicit_name if contact_level=='verified' else (_cloud_contact_name_from_email(email) or explicit_name)
            compact_local = re.sub(r'[^a-z0-9]+', '', _contact_local(email))
            standard_allowed=automatic_addressbook_contact_allowed(email, name or explicit_name)
            if not standard_allowed and not (contact_level=='broad' and broad_shared_contact_allowed(email)):
                continue
            validated.append({
                'email': email,
                'name': clean_contact_name(name, company),
                'company': company[:200],
                'source_url': item.get('source_url', ''),
                'generic': False,
                'confidence': _int(d.get('confidence'), 70),
                'notes': ('Cloud Web contact validation: ' + str(d.get('reason') or 'Public contact verified for direct outreach.'))[:2000],
                'company_summary': item.get('company_summary', ''),
                'company_country': _clean_company_country(item.get('company_country', '')),
                'company_intel': item.get('company_intel') if isinstance(item.get('company_intel'),dict) else {},
                'evidence_text': (str(item.get('title') or '')+' '+str(item.get('page_excerpt') or ''))[:8000],
            })
    dedup = {x['email']: x for x in validated}
    return list(dedup.values()), {
        'candidates': len(candidates),
        'validated': len(dedup),
        'rejected': max(0, len(candidates) - len(dedup)),
        'requests': requests,
    }


def persist_cloud_contacts(contact_rows, source_name='Cloud Web'):
    """Persist validated Cloud Web contacts through the shared Address Book policy."""
    created = 0
    for item in contact_rows or []:
        email = str(item.get('email') or '').strip().lower()
        if not email or _cloud_contact_noise(email):
            continue
        contact, was_created, _outcome = maybe_persist_addressbook_contact(
            email,
            name=str(item.get('name') or _cloud_contact_name_from_email(email))[:200],
            company=str(item.get('company') or _domain_company(email) or '')[:200],
            source=source_name[:120],
            source_url=str(item.get('source_url') or '')[:1000],
            confidence=_int(item.get('confidence'), 70),
            notes=str(item.get('notes') or 'Public email validated from a URL returned by Cloud Web research.')[:2000],
            company_summary=str(item.get('company_summary') or company_summary_from_intel(item.get('company_intel') if isinstance(item.get('company_intel'),dict) else {},1200) or '')[:2000],
            company_country=_clean_company_country(item.get('company_country')),
            company_intel=item.get('company_intel') if isinstance(item.get('company_intel'),dict) else {},
            require_company_match=True,
            queue_research=False,
            evidence_text=str(item.get('evidence_text') or '')[:8000],
        )
        if contact is not None and was_created:
            created += 1
    return created


def _cloud_hidden_lead_summary(row):
    """Return descriptive company prose, never a structured engagement/remote enum."""
    row=row if isinstance(row,dict) else {}
    engagement=' '.join(str(row.get('engagement_type') or row.get('employment_type') or '').split()).strip().casefold()
    enum_values={'full time','part time','contract','contractor','collaboration','agency consulting','one time project','unknown','fully remote','remote','hybrid','onsite','on site'}
    for key in ('summary','snippet'):
        text=strip_hidden_lead_evidence_markers(' '.join(str(row.get(key) or '').split()).strip())
        if not text:
            continue
        normalized=re.sub(r'[_-]+',' ',text.casefold())
        normalized=re.sub(r'\s+',' ',normalized).strip(' .,:;')
        engagement_normalized=re.sub(r'[_-]+',' ',engagement)
        engagement_normalized=re.sub(r'\s+',' ',engagement_normalized).strip()
        if normalized in enum_values or (engagement_normalized and normalized==engagement_normalized):
            continue
        return text[:4000]
    return ''


def _cloud_lead_company_intel(row, company, url):
    """Preserve company context returned by the Cloud discovery pass itself.

    Hidden Leads used to discard these fields and therefore showed '?' until someone
    opened the detail page and manually/automatically ran Company Research.
    """
    row=row if isinstance(row,dict) else {}
    facts=[]
    summary=_cloud_hidden_lead_summary(row) or ' '.join(str(row.get('lead_reason') or '').split()).strip()
    if summary: facts.append({'label':'What they do','value':summary[:800],'verification':'verified' if row.get('sources') else 'estimate'})
    size=' '.join(str(row.get('company_size') or row.get('employee_count_or_range') or '').split()).strip()
    if size: facts.append({'label':'Size/structure','value':size[:300],'verification':'verified' if row.get('sources') else 'estimate'})
    founded=''
    m=re.search(r'\b(18|19|20)\d{2}\b',str(row.get('founded_year') or ''))
    if m:
        founded=int(m.group(0)); facts.append({'label':'Founded','value':str(founded),'verification':'verified' if row.get('sources') else 'estimate'})
    if row.get('founded_by'): facts.append({'label':'Founded by','value':str(row.get('founded_by'))[:500],'verification':'verified' if row.get('sources') else 'estimate'})
    sources=[]
    for x in row.get('sources') or []:
        if isinstance(x,str) and x.startswith(('http://','https://')): sources.append({'provider':'Cloud Web','title':x,'url':x})
        elif isinstance(x,dict) and str(x.get('url') or '').startswith(('http://','https://')): sources.append({'provider':str(x.get('provider') or 'Cloud Web')[:120],'title':str(x.get('title') or x.get('url'))[:300],'url':str(x.get('url'))[:1000]})
    if url and not any(x.get('url')==url for x in sources): sources.insert(0,{'provider':'Cloud Web','title':'Lead source','url':url})
    structured={'founded_year':founded or '', 'founded_by':str(row.get('founded_by') or '')[:500], 'age_range':'', 'size_range':'', 'verified':bool(sources)}
    if founded:
        years=max(0,timezone.localdate().year-founded)
        structured['age_range']='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
    sm=re.search(r'(?<!\d)(\d{1,6})\s*(?:[–—-]|to)\s*(\d{1,6})(?!\d)',size,re.I)
    if sm: structured['size_range']=f'{int(sm.group(1)):,}–{int(sm.group(2)):,}'
    else:
        sm=re.search(r'(?<!\d)(\d{1,6})\s*(\+)?\s*(?:employees?|people|staff)',size,re.I)
        if sm: structured['size_range']=f'{int(sm.group(1)):,}'+('+' if sm.group(2) else '')
    return {'company':company,'confidence':max(25,min(98,int(row.get('confidence') or row.get('_lead_qualification_confidence') or 55))), 'facts':facts[:12], 'structured':structured, 'sources':sources[:12], 'errors':[], 'status':'complete' if facts else 'collecting', 'updated_at':timezone.now().isoformat(), 'cloud_native':True}


def persist_cloud_hidden_leads(campaign, source, rows):
    created = 0
    ids = []
    for row in rows or []:
        company = str(row.get('company') or '').strip()[:220]
        url = str(row.get('_inspected_url') or row.get('url') or '').strip()[:1000]
        evidence_text=' '.join(str(row.get(k) or '') for k in ('title','lead_reason','summary','evidence','snippet','_page_text'))
        if not company or not url or _lead_final_url_invalid(url) or is_blacklisted_url(url, scope='hidden_leads', company=company) or adult_content_reason(str(row.get('title') or company),evidence_text,url):
            continue
        # A concrete active Opportunity wins over a generic company lead.
        if active_opportunity_for_company(company, url):
            continue
        # 0.11.8 Hidden Leads only: qualify the identified URL with a bounded
        # minibrowser and LLM cutoff before creating a new lead.  Existing leads are
        # still only updated after duplicate lookup below; Opportunities and Address
        # Book are not part of this gate.
        try:
            lead_gate=hidden_lead_minibrowser_admission(
                campaign,url,company,initial_title=str(row.get('title') or company),
                initial_text=str(row.get('_page_text') or row.get('summary') or row.get('snippet') or ''),
                evidence=' '.join(str(row.get(k) or '') for k in ('lead_reason','evidence','snippet')),
                hits=[x for x in re.findall(r'[A-Za-z][A-Za-z0-9+#./-]{2,}', evidence_text)[:12]],
                max_pages=6,cutoff=int(lead_policy(selectivity_current('hidden_leads')).get('minibrowser_cutoff') or 75),
            )
        except Exception as exc:
            lead_gate={'admit':False,'decision':'reject','lead_score':0,'reason':'hidden_lead_minibrowser_error','model_error':str(exc)[:500]}
        lead_level=selectivity_current('hidden_leads'); lead_rules=lead_policy(lead_level)
        if lead_rules.get('requires_campaign_anchor') and lead_gate.get('admit'):
            strict_ok,strict_hits=campaign_alignment(campaign,lead_gate.get('company_name') or company,' '.join(str(lead_gate.get(k) or '') for k in ('summary','why_relevant','reason_to_contact'))+' '+evidence_text,level=lead_level,kind='hidden_lead')
            row['_lead_selectivity']={'level':lead_level,'campaign_hits':strict_hits}
            if not strict_ok:
                lead_gate=dict(lead_gate); lead_gate['admit']=False; lead_gate['decision']='reject'; lead_gate['reason']='selectivity_missing_campaign_anchor'
        if not lead_gate.get('admit'):
            UsageMetric.objects.create(category='discovery_filter',provider=source.name if source else 'cloud_web',stage='hidden_lead_minibrowser_admission',requests=1,pages=len(lead_gate.get('pages') or []),metadata={'url':url,'company':company,'decision':lead_gate.get('decision'),'lead_score':lead_gate.get('lead_score'),'cutoff':lead_gate.get('cutoff'),'selectivity':lead_level,'reason':lead_gate.get('reason_to_contact') or lead_gate.get('why_relevant') or lead_gate.get('reason') or 'Hidden Lead admission score below cutoff.','rejection_risks':lead_gate.get('rejection_risks')})
            continue
        if lead_gate.get('company_name'):
            company=str(lead_gate.get('company_name') or company).strip()[:220] or company
        row['_hidden_lead_minibrowser_admission']=lead_gate
        cloud_company_intel=_cloud_lead_company_intel(row,company,url)
        host = ''
        try:
            host = urlsplit(url).netloc.lower().removeprefix('www.')
        except Exception:
            pass
        existing = active_duplicate_lead(company, url)
        if not existing:
            existing = CompanyLead.objects.filter(user_deleted=False, company__iexact=company).first()
        if not existing and host:
            existing = CompanyLead.objects.filter(user_deleted=False).filter(Q(target_url__icontains=host) | Q(source_url__icontains=host)).first()
        if existing:
            lead = existing
            changed = []
            if not lead.source_id and source:
                lead.source = source; changed.append('source')
            if url and lead.target_url != url:
                lead.target_url = url; changed.append('target_url')
            if not lead.source_url:
                lead.source_url = url; changed.append('source_url')
            if row.get('country') and not lead.country:
                lead.country = _clean_company_country(row.get('country')); changed.append('country')
            if row.get('lead_reason'):
                lead.match_summary = str(row.get('lead_reason'))[:2000]; changed.append('match_summary')
            if row.get('_http_status') is not None:
                lead.target_http_status = int(row.get('_http_status') or 0); changed.append('target_http_status')
                lead.target_checked_at = timezone.now(); changed.append('target_checked_at')
                lead.target_check_error = str(row.get('_check_error') or '')[:500]; changed.append('target_check_error')
            validated_email = ((row.get('_validated_emails') or [''])[0] or '').strip()[:254] if row.get('_validated_emails') else ''
            if validated_email and not lead.contact_email:
                lead.contact_email = validated_email; changed.append('contact_email')
            contact_url = _lead_contact_url(row, url)
            if contact_url and not lead.contact_url:
                lead.contact_url = contact_url; changed.append('contact_url')
            existing_intel=lead.company_intel if isinstance(lead.company_intel,dict) else {}
            existing_struct=existing_intel.get('structured') if isinstance(existing_intel.get('structured'),dict) else {}
            cloud_struct=cloud_company_intel.get('structured') if isinstance(cloud_company_intel.get('structured'),dict) else {}
            existing_display=bool(existing_struct.get('founded_year') or existing_struct.get('age_range') or existing_struct.get('domain_age_label') or existing_struct.get('size_range'))
            cloud_display=bool(cloud_struct.get('founded_year') or cloud_struct.get('age_range') or cloud_struct.get('domain_age_label') or cloud_struct.get('size_range'))
            if cloud_company_intel.get('facts') and (not existing_intel.get('facts') or existing_intel.get('status')!='complete' or (cloud_display and not existing_display)):
                lead.company_intel=cloud_company_intel; changed.append('company_intel')
            if changed:
                lead.save(update_fields=list(dict.fromkeys(changed + ['updated_at'])))
        else:
            lead_gate=row.get('_hidden_lead_minibrowser_admission') if isinstance(row.get('_hidden_lead_minibrowser_admission'),dict) else {}
            evidence = str(lead_gate.get('text') or row.get('_page_text') or row.get('evidence') or row.get('snippet') or '')[:12000]
            lead = CompanyLead.objects.create(
                company=company,
                source=source,
                country=_clean_company_country(row.get('country')),
                match_summary=str(row.get('lead_reason') or 'Cloud Web research verified this as a directly actionable specialist outreach target.')[:2000],
                summary=(strip_hidden_lead_evidence_markers(lead_gate.get('summary')) or _cloud_hidden_lead_summary(row)),
                evidence=evidence,
                company_intel=cloud_company_intel,
                search_url=str(row.get('url') or '')[:1000],
                target_url=url,
                source_url=url,
                contact_email=(clean_contact_email((row.get('_validated_emails') or [''])[0]) if row.get('_validated_emails') and assignable_contact_email((row.get('_validated_emails') or [''])[0]) else ''),
                contact_url=_lead_contact_url(row, url),
                score=max(25, min(100, int((lead_gate.get('lead_score') if lead_gate else None) or row.get('_lead_qualification_confidence') or row.get('_pre_score') or row.get('confidence') or 50))),
                status='review',
                note='',
                target_http_status=int(row.get('_http_status') or 0) if row.get('_http_status') is not None else None,
                target_checked_at=timezone.now() if row.get('_http_status') is not None else None,
                target_check_error=str(row.get('_check_error') or '')[:500],
            )
            created += 1
        attribute_campaign(lead,campaign)
        try:
            state=dict(lead.ai_state or {})
            state['provenance']={'type':'discovered_company','source':'cloud_web','at':timezone.now().isoformat()}
            if isinstance(row.get('_hidden_lead_minibrowser_admission'),dict):
                state['hidden_lead_minibrowser_admission']={k:v for k,v in row.get('_hidden_lead_minibrowser_admission').items() if k!='text'}
            state['hidden_lead_score']={
                'technical_relevance':max(0,min(100,int(row.get('_lead_qualification_confidence') or row.get('_pre_score') or row.get('confidence') or lead.score or 50))),
                'company_confidence':max(0,min(100,int(row.get('_company_confidence') or row.get('confidence') or 70))),
                'contactability':80 if lead.contact_email or lead.contact_url else 35,
                'provenance_type':'discovered_company',
            }
            lead.ai_state=state; lead.save(update_fields=['ai_state','updated_at'])
        except Exception:
            pass
        if lead.contact_email:
            try:
                maybe_persist_addressbook_contact(
                    lead.contact_email,name=lead.contact_name,company=lead.company,source='Cloud Web Hidden Lead',
                    source_url=lead.target_url or lead.source_url,confidence=max(70,int(lead.score or 0)),
                    company_summary=lead.summary,company_country=lead.country,company_intel=lead.company_intel,
                    require_company_match=True,queue_research=False,
                )
            except Exception:
                pass
        if lead.pk not in ids:
            ids.append(lead.pk)
    return {'created': created, 'ids': ids}



def research_hiring_signal(campaign, candidate, page_text='', anchor=None):
    """Verify one community/forum item as an actionable company hiring signal.

    Unlike ``research_candidate`` this route does not require a canonical vacancy URL.
    Reddit/Hacker News/forum posts are evidence about an employer, not the employer
    identity itself. The result is intentionally shaped like ScoutBox's semantic lead
    review so discovery can persist it as a Hidden Lead without invoking Local AI.
    """
    anchor = anchor or effective_cloud_bundle_anchor(start_stage='jd_analysis')
    if not anchor:
        return None
    profile = Profile.objects.get_or_create(pk=1)[0]
    role = (_campaign_list(campaign.role_families) or [candidate.get('title') or 'specialist technical work'])[0]
    _selected, role_definition, specialist, _titles = _select_cv_and_role_brief(campaign, role)
    compact = {
        'url': candidate.get('url') or candidate.get('target_url') or '',
        'title': candidate.get('title') or '',
        'claimed_company': candidate.get('company') or '',
        'source_kind': candidate.get('_community_kind') or candidate.get('_direct_adapter') or 'community',
        'search_snippet': candidate.get('snippet') or '',
        'page_excerpt': str(page_text or '')[:12000],
    }
    prompt = f'''Assess this one community/forum item as a possible hiring signal for ScoutBox.
Target work: {role_definition}.
Relevant candidate evidence: {', '.join(specialist[:12])}.
{_discovery_preferences_text(profile, campaign)}

The supplied URL may be Reddit, Hacker News, a forum, or another community platform. Treat that URL as evidence only; NEVER use the platform (Reddit, Hacker News, etc.) as the employer. Identify the actual employer/company only when the evidence or grounded web research supports it. Do not invent a company.

Keep the signal only when it indicates a real current/recent hiring need, contract/project need, or directly useful specialist outreach target AND the need is relevant to the candidate profile. A generic discussion, career advice, old anecdote, recruiter spam, news with no hiring implication, or merely topical overlap must be rejected. A canonical vacancy URL is NOT required for a Hidden Lead.

Return JSON only, exactly one object with these fields:
{{
  "qualify": true|false,
  "purpose": "company_hiring_signal"|"company_outreach_target"|"job_opportunity"|"contract_project"|"other",
  "company_name": "actual employer or empty",
  "company_country": "country or empty",
  "role_title": "role/need if known",
  "profile_relevant": true|false,
  "relevance_confidence": 0-100,
  "confidence": 0-100,
  "fit_score": 0-100,
  "actionable": true|false,
  "lead_actionable": true|false,
  "reason": "concise evidence-based reason",
  "lead_reason": "why this is worth outreach/review",
  "evidence": "short factual evidence",
  "sources": ["supporting URLs"]
}}

Signal:
{json.dumps(compact, ensure_ascii=False)}'''
    try:
        mark_candidates(1, deep=True)
    except CloudLimitReached:
        return None
    stage = anchor.get('stage') or 'jd_analysis'
    try:
        with scoped_usage_context(bundle_anchor=stage, bundled_activities=['community hiring-signal verification']):
            text, meta = cloud_web_search(prompt, timeout=180, route_lane=anchor.get('lane'), stage=stage)
    except Exception:
        return None
    data = _extract_json(text)
    row = data
    if isinstance(data.get('results'), list) and data.get('results'):
        row = data['results'][0] if isinstance(data['results'][0], dict) else {}
    if not isinstance(row, dict):
        return None
    purpose = str(row.get('purpose') or 'other').strip().lower()
    if purpose not in {'company_hiring_signal','company_outreach_target','job_opportunity','contract_project','other'}:
        purpose = 'other'
    qualify = _bool(row.get('qualify'))
    profile_relevant = _bool(row.get('profile_relevant'))
    confidence = _int(row.get('confidence'), 0)
    relevance = _int(row.get('relevance_confidence'), 0)
    actionable = _bool(row.get('actionable'))
    lead_actionable = _bool(row.get('lead_actionable')) or actionable
    company = ' '.join(str(row.get('company_name') or row.get('company') or '').split()).strip()[:220]
    if not qualify or not profile_relevant or confidence < 60 or relevance < 55 or not lead_actionable or not company:
        return None
    sources = _sources(row, meta)
    return {
        'purpose': purpose,
        'company_name': company,
        'company_country': _clean_company_country(row.get('company_country') or row.get('country') or ''),
        'role_title': ' '.join(str(row.get('role_title') or row.get('role') or '').split()).strip()[:300],
        'profile_relevant': True,
        'relevance_confidence': max(0,min(100,relevance)),
        'confidence': max(0,min(100,confidence)),
        'fit_score': max(0,min(100,_int(row.get('fit_score'), relevance))),
        'actionable': actionable,
        'lead_actionable': lead_actionable,
        'reason': str(row.get('reason') or row.get('evidence') or '')[:2000],
        'lead_reason': str(row.get('lead_reason') or row.get('reason') or '')[:2000],
        'evidence': str(row.get('evidence') or '')[:6000],
        'sources': sources,
        'cloud_provider': str(meta.get('provider') or '')[:120],
        'cloud_model': str(meta.get('model') or '')[:160],
    }

def research_candidate(campaign, candidate, page_text='', anchor=None):
    """Focused Cloud enrichment for one Local AI Discovery candidate; no full profile/campaign dump."""
    anchor = anchor or effective_cloud_bundle_anchor(start_stage='jd_analysis')
    if not anchor:
        return None
    profile = Profile.objects.get_or_create(pk=1)[0]
    role = (_campaign_list(campaign.role_families) or [candidate.get('title') or 'specialist technical work'])[0]
    selected, role_definition, specialist, _titles = _select_cv_and_role_brief(campaign, role)
    compact = {'url': candidate.get('url') or candidate.get('target_url') or '', 'title': candidate.get('title') or '', 'company': candidate.get('company') or '', 'search_snippet': candidate.get('snippet') or '', 'page_excerpt': str(page_text or '')[:10000]}
    prompt = f'''Research this one opportunity. Target work: {role_definition}. Relevant CV evidence: {', '.join(specialist[:12])}. {_discovery_preferences_text(profile, campaign)} Pay/company size/engagement are ranking preferences only, never rejection reasons when missing.

Resolve an exact item URL, remote eligibility, current status, fit and posting-age evidence. If this candidate came from a third-party listing, search for the same role on the employer's own site and prefer the exact direct-company posting when verified; never replace it with a generic careers page. For age you may use ordinary web research including public archive.org evidence when useful, but never an archive.org API. Return JSON only with one results row using the standard ScoutBox opportunity fields.

Candidate:\n{json.dumps(compact, ensure_ascii=False)}'''
    try:
        mark_candidates(1, deep=True)
    except CloudLimitReached:
        return None
    provider, model, stage = anchor.get('provider'), anchor.get('model'), anchor.get('stage') or 'jd_analysis'
    try:
        with scoped_usage_context(bundle_anchor=stage, bundled_activities=['single-candidate verification']):
            # Reuse the resilient Cloud route instead of calling one model directly. This
            # gets Gemini empty-output recovery, structured-response retry and configured
            # failover for direct/forum candidate qualification too.
            text, meta = cloud_web_search(prompt, timeout=180, route_lane=anchor.get('lane'), stage=stage)
    except Exception:
        return None
    rows = _clean_results(text, meta, limit=1, allow_generic=False)
    if not rows:
        return None
    researched = rows[0]
    if researched.get('remote_status') not in REMOTE_ACCEPTED or int(researched.get('remote_confidence') or 0) < 55:
        return None
    researched['cloud_discovery'] = True
    return researched


def discover(campaign, max_results=None, test=False, test_instruction=''):
    """Concise role-specific Cloud Web discovery with content-based CV selection and resilient verification."""
    cfg = PortalSettings.objects.get_or_create(pk=1)[0]
    profile = Profile.objects.get_or_create(pk=1)[0]
    max_results = min(int(max_results or cfg.cloud_discovery_candidates_per_run or 50), int(cfg.cloud_test_candidates if test else cfg.cloud_discovery_candidates_per_run or 50), 60)
    roles = _campaign_list(campaign.role_families)
    test_instruction = str(test_instruction or '').strip()[:500]
    if test and test_instruction:
        roles = [test_instruction]
    elif test:
        roles = roles[:1]
    if not roles:
        profile_scope=profile.scope_json if isinstance(profile.scope_json,dict) else {}
        roles=[str(x).strip() for x in (profile_scope.get('likely_roles') or []) if str(x).strip()][:8]
    if not roles:
        raise RuntimeError('Candidate Profile has no reliable likely roles for Cloud Web discovery. Review/rebuild the Candidate Profile instead of using a generic profession fallback.')
    # Each pass is one role. No role/profile dump from other campaign families.
    roles = roles[:8]
    search_budget = int(cfg.cloud_test_searches_per_run or 20) if test else int(cfg.cloud_web_searches_per_run or 100)
    per_role = max(3, min(16, search_budget // max(1, len(roles))))
    market_offset=int(timezone.now().timestamp()//max(1800,int(getattr(cfg,'scraper_interval_minutes',120) or 120)*60))
    coverage=market_plan(cfg,campaign_id=getattr(campaign,'pk',0),rotation_offset=market_offset)
    markets=coverage['markets']
    current_usage=usage_context()
    custom_instruction = str(current_usage.get('custom_instructions') or '').strip()[:1500]
    preferred=[str(x).strip() for x in (current_usage.get('preferred_company_countries') or []) if str(x).strip()][:20]
    excluded=[str(x).strip() for x in (current_usage.get('excluded_company_countries') or []) if str(x).strip()][:20]
    blocks=[]
    if custom_instruction: blocks.append('[custom instruction] '+custom_instruction)
    if preferred: blocks.append('[prefer company in] '+', '.join(preferred))
    if excluded: blocks.append('[exclude company in] '+', '.join(excluded))
    custom_domains=list(CustomSearchDomain.objects.filter(enabled=True).order_by('name','domain')[:20])
    if custom_domains:
        blocks.append('[custom domain research targets] '+', '.join(_custom_domain_url(x.domain) for x in custom_domains)+'. Explicitly check these domains for recent relevant opportunities/hiring signals; do not route through Local Search Sources or Ollama.')
    # These are research instructions only. They are appended to the initial Cloud AI query and
    # deliberately do not become deterministic/local post-filters or later-stage prompt baggage.
    custom_block=('\n\n'+'\n'.join(blocks)) if blocks else ''

    raw_rows, raw_texts, prompts, role_briefs = [], [], [], []
    first_meta, provider_names, model_names = {}, [], []
    selected_cv_ids = []
    per_role_limit = max(5, min(20, max_results + 4 if len(roles) == 1 else max(6, (max_results + len(roles) - 1) // len(roles) + 3)))
    max_passes=max(len(roles),min(8,max(1,search_budget//max(3,per_role))))
    passes=[]
    if markets:
        for idx in range(max_passes): passes.append((roles[idx % len(roles)], markets[idx % len(markets)],None))
    else:
        passes=[(role,None,None) for role in roles]
    multilingual=multilingual_assignments(cfg,markets,rotation_offset=market_offset)
    for idx,assignment in enumerate(multilingual):
        passes.append((roles[idx%len(roles)],assignment['market'],assignment))
    multilingual_executed=[]
    market_allocations={}
    for role, discovery_market, multilingual_assignment in passes:
        selected, definition, specialist, titles = _select_cv_and_role_brief(campaign, role)
        if selected and selected.get('id') not in selected_cv_ids:
            selected_cv_ids.append(selected.get('id'))
        role_briefs.append({'role': role, 'definition': definition, 'specialist_terms': specialist, 'title_angles': titles, 'selected_cv_id': selected.get('id') if selected else None})
        market_block=custom_block
        if discovery_market:
            market_block += f'\n[discovery market] Search specifically within {discovery_market.name}; use market-appropriate sources and local domains where useful. Candidate operating locations are preferences, not an acquisition filter.'
            market_allocations[discovery_market.code]=market_allocations.get(discovery_market.code,0)+1
        if multilingual_assignment:
            language=multilingual_assignment['language']
            market_block += f'\n[multilingual supplemental pass] Run this supplemental pass using concise {language} equivalents of the specialist search concepts. Keep English interpretation in every returned structured field, preserve original-language source text and URLs, and return only results meeting the normal or stricter relevance and opportunity-quality requirements.'
        rows, text, meta, prompt = _research_role(campaign, role, selected, definition, specialist, titles, per_role_limit, per_role, market_block, test)
        if multilingual_assignment:
            multilingual_executed.append(multilingual_assignment['id'])
        for row in rows:
            if discovery_market: row['_discovery_market']=discovery_market.name; row['_discovery_market_code']=discovery_market.code
            if multilingual_assignment: row['_multilingual_language']=multilingual_assignment['language']; row['_multilingual_source']=multilingual_assignment['source']
        role_index=len(role_briefs)-1
        for row in rows:
            row['_role_index']=role_index
            row['_primary_role']=role
        raw_rows.extend(rows); raw_texts.append(text); prompts.append(prompt)
        if not first_meta:
            first_meta = meta
        if meta.get('provider') and meta.get('provider') not in provider_names:
            provider_names.append(meta.get('provider'))
        if meta.get('model') and meta.get('model') not in model_names:
            model_names.append(meta.get('model'))
        if discovery_market:
            UsageMetric.objects.create(category='discovery_market',provider=str(meta.get('provider') or 'Cloud Web'),stage='query',requests=1,pages=len(rows or []),metadata={'market_code':discovery_market.code,'market':discovery_market.name,'multilingual_language':multilingual_assignment['language'] if multilingual_assignment else '','multilingual':bool(multilingual_assignment)})

    custom_domain_routes=[]
    if custom_domains and role_briefs:
        for domain_obj in custom_domains:
            domain_rows,domain_text,domain_meta,route_name=_research_custom_domain(campaign,domain_obj,role_briefs[0],min(6,per_role),test=test)
            custom_domain_routes.append({'domain':domain_obj.domain,'route':route_name,'results':len(domain_rows)})
            for row in domain_rows:
                row['_role_index']=0
                row['_primary_role']=role_briefs[0].get('role') or roles[0]
                row['_custom_domain']=domain_obj.domain
            raw_rows.extend(domain_rows)
            if domain_text:
                raw_texts.append('CUSTOM DOMAIN '+domain_obj.domain+'\n'+domain_text)
            if domain_meta.get('provider') and domain_meta.get('provider') not in provider_names:
                provider_names.append(domain_meta.get('provider'))
            if domain_meta.get('model') and domain_meta.get('model') not in model_names:
                model_names.append(domain_meta.get('model'))

    # Directly inspect every URL returned by Cloud AI before deciding its destination.
    _inspect_cloud_urls(raw_rows)
    deduped, seen = [], set()
    for row in raw_rows:
        key = (str(row.get('url') or ''), str(row.get('title') or '').casefold(), str(row.get('company') or '').casefold())
        if key in seen:
            continue
        seen.add(key); deduped.append(row)
    deduped.sort(key=lambda r: (int(r.get('_pre_score') or 0), int(r.get('confidence') or 0)), reverse=True)
    shortlist = [r for r in deduped if r.get('disposition') != 'hidden_lead'][:max_results * 2]
    pre_hidden = [r for r in deduped if r.get('disposition') == 'hidden_lead']

    # Trim to available deep-research capacity instead of failing an entire run.
    deep_capacity = _remaining_deep_capacity(cfg)
    shortlist = shortlist[:deep_capacity]
    if shortlist:
        mark_candidates(len(shortlist), deep=False)
        mark_candidates(len(shortlist), deep=True)

    resolved, hidden, verify_text_parts, verify_meta, retries = [], [], [], {}, 0
    verified_total=0; unresolved_total=0
    if shortlist:
        # Verification stays one-role-at-a-time too. A multi-role campaign is several independent
        # research passes; candidates never inherit the first role's brief by accident.
        groups={}
        for row in shortlist:
            groups.setdefault(int(row.get('_role_index') or 0),[]).append(row)
        for role_index, group in groups.items():
            rb=role_briefs[role_index] if 0 <= role_index < len(role_briefs) else role_briefs[0]
            r,h,text,meta,rr=_resolve_candidates(group, rb['definition'], rb['specialist_terms'], profile, campaign, per_role, '')
            resolved.extend(r); hidden.extend(h); retries+=rr
            if text: verify_text_parts.append(text)
            if meta:
                verify_meta=meta
                verified_total+=int(meta.get('_verified_count') or 0)
                unresolved_total+=int(meta.get('_unresolved_count') or 0)
    verify_text='\n\n--- role verification ---\n'.join(verify_text_parts)
    hidden = pre_hidden + hidden
    hidden, lead_qualification = _qualify_hidden_leads(campaign, hidden, role_briefs, per_role, '')
    if shortlist and verified_total == 0:
        raise RuntimeError('Cloud verification returned no valid structured rows after smaller-batch retries; the provider response appears incomplete or malformed.')
    resolved.sort(key=lambda r: (int(r.get('_pre_score') or 0), int(r.get('confidence') or 0)), reverse=True)
    rows = resolved[:max_results]

    # Inspect and mine contacts only from records that can actually survive this run:
    # persisted opportunity candidates plus qualified hidden leads. This prevents a
    # lower-ranked/discarded Cloud candidate from polluting Address Book.
    final_inspected = _inspect_final_rows(list(rows) + list(hidden))
    contact_rows, contact_qualification = _qualify_cloud_contacts(list(rows) + list(hidden), campaign)
    validated_by_company = {}
    for contact in contact_rows:
        validated_by_company.setdefault(str(contact.get('company') or '').strip().casefold(), []).append(contact.get('email'))
    for row in rows:
        row['_validated_emails'] = [e for e in validated_by_company.get(str(row.get('company') or '').strip().casefold(), []) if e]
    for lead in hidden:
        lead['_validated_emails'] = [e for e in validated_by_company.get(str(lead.get('company') or '').strip().casefold(), []) if e]

    provider = verify_meta.get('provider') or (provider_names[0] if provider_names else first_meta.get('provider', ''))
    model = verify_meta.get('model') or (model_names[0] if model_names else first_meta.get('model', ''))
    source_name = {'openai': 'OpenAI', 'gemini': 'Gemini', 'openrouter': 'OpenRouter'}.get(str(provider).lower(), str(provider or 'Cloud AI').title())
    source, _ = SearchSource.objects.update_or_create(name=source_name, defaults={
        'category': 'Cloud AI discovery', 'source_type': 'cloud_ai', 'enabled': True, 'priority': 100,
        'adapter_status': 'routing', 'notes': 'Internal Cloud discovery provenance. Execution is controlled only by Discovery Mode.',
    })
    stat, _ = SearchProviderStat.objects.get_or_create(source=source, day=timezone.localdate())
    stat.requests += len(passes) + (len(shortlist) + 1) // 2 + retries
    stat.results += len(rows)
    stat.save(update_fields=['requests', 'results'])
    return {
        'results': rows, 'hidden_leads': hidden, 'contact_rows': contact_rows,
        'source': source, 'provider': provider, 'model': model, 'providers': provider_names, 'models': model_names,
        'queries': roles, 'role_briefs': role_briefs,
        'search_profile': {'cv_count': len(extract_active_cv_texts()), 'selected_cv_ids': selected_cv_ids, 'skills': []},
        'test_instruction': test_instruction,
        'raw_text': ('\n\n--- role pass ---\n'.join(raw_texts) + '\n\n--- eligibility resolver ---\n' + verify_text)[:100000],
        'cloud_native': True, 'deep_researched': len(shortlist), 'role_passes': len(roles),
        'rejected_before_persistence': max(0, len(shortlist) - len(rows)), 'resolver_retries': retries,
        'urls_returned': len(raw_rows), 'urls_inspected': sum(1 for r in raw_rows if r.get('_page_ok')),
        'deep_capacity_remaining_before_run': deep_capacity, 'prompt_chars': [len(p) for p in prompts],
        'verified_candidates': verified_total, 'unresolved_after_retries': unresolved_total,
        'final_urls_inspected': final_inspected,
        'hidden_lead_candidates': lead_qualification.get('candidates', 0),
        'hidden_leads_qualified': lead_qualification.get('qualified', 0),
        'hidden_leads_rejected': lead_qualification.get('rejected', 0),
        'hidden_lead_qualification_requests': lead_qualification.get('requests', 0),
        'contact_candidates': contact_qualification.get('candidates', 0),
        'contacts_validated': contact_qualification.get('validated', 0),
        'contacts_rejected': contact_qualification.get('rejected', 0),
        'contact_validation_requests': contact_qualification.get('requests', 0),
        'custom_domain_routes': custom_domain_routes,
        'market_coverage':{**{k:v for k,v in coverage.items() if k!='markets'},'allocation':market_allocations},
        'multilingual_exploration':{'enabled':True,'strength':str(getattr(cfg,'multilingual_exploration_strength','balanced') or 'balanced'),'planned':len(multilingual),'executed':len(set(multilingual_executed)),'languages':[x['language'] for x in multilingual]},
    }
