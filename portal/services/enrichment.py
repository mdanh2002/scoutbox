import json
import re
import time
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from portal.models import Opportunity, OpportunityEvidence, PortalSettings, Profile, UsageMetric, Contact
from .mailbox import is_generic, contact_company_from_email, contact_name_from_email
from .presentation import clean_placeholder
from .ai import generate, LocalAILaneBusy
from .search import facebook_authenticated_fetch, UA
from .history import evaluate_company_history
from .role_gate import classify_role_page
from .pagefetch import detect_language, clean_visible_text, structured_visible_text
from .languages import preferred_language_delta
from .highlights import normalize_ai_fit_summary, derive_opportunity_highlight
from .salary import normalized_pay_preferences
from .content_quality import extract_role_location
from .cold import infer_country

EMAIL_RE=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


def _extract_jsonld(soup):
    jobs=[]
    for tag in soup.find_all('script',type='application/ld+json'):
        try:
            data=json.loads(tag.string or tag.get_text() or '{}')
        except Exception:
            continue
        items=data if isinstance(data,list) else [data]
        for item in items:
            if isinstance(item,dict) and item.get('@type')=='JobPosting': jobs.append(item)
            if isinstance(item,dict) and isinstance(item.get('@graph'),list):
                jobs.extend([x for x in item['@graph'] if isinstance(x,dict) and x.get('@type')=='JobPosting'])
    return jobs[0] if jobs else {}


def _parse_dt(value):
    if not value: return None
    try:
        v=str(value).replace('Z','+00:00')
        dt=datetime.fromisoformat(v)
        return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
    except Exception:
        return None


def _llm_fit_remote(opportunity, text, profile):
    """Classify candidate fit and working arrangement from the actual opportunity evidence.

    This deliberately avoids keyword/regex rules for remote status and fit. The configured
    model sees the cleaned role text plus the candidate priorities and engagement settings,
    then returns a small structured classification. If no model is available the existing
    discovery score is preserved and remote status remains unknown rather than guessed.
    """
    facts=dict(opportunity.extracted_facts or {})
    scope=dict(profile.scope_json or {})
    preference_scope={
        'operating_locations':profile.operating_locations or ([profile.operating_location] if profile.operating_location else []),
        'high_priority':profile.high_priority_text or '',
        'medium_priority':profile.medium_priority_text or '',
        'low_priority':profile.low_priority_text or '',
        'engagement_types':scope.get('engagement') or [],
        'company_sizes':scope.get('company_size') or [],
        'pay_preferences':normalized_pay_preferences(scope),
        'hiring_process_guidance':scope.get('interview_notes') or '',
    }
    prompt=(
        'Classify this work opportunity against the candidate preferences and the supplied page evidence. '
        'Use the actual meaning of the text, not simple keyword matching. Do not invent facts. '
        'For remote_status choose exactly one of: fully_remote, remote, hybrid, onsite, unknown. '
        'fully_remote means the role is clearly remote with no meaningful regular site requirement; remote means remote work is allowed but geography or occasional presence is unclear; '
        'hybrid means both remote and regular on-site/office work are expected; onsite means the work is primarily site/office based or the duties clearly require physical presence; unknown means the evidence is insufficient. '
        'Do not treat phrases such as remote monitoring, remote access, or remote systems as proof that the job itself is remote. '
        'Assess technical relevance using the candidate priorities. Compensation/pay threshold, company size, engagement type, and hiring-process preferences are SOFT ranking signals only: missing values are neutral, and known mismatches may lower fit but must never by themselves produce Reject. '
        "This product searches niche work, so preserve otherwise relevant opportunities when only a few matches exist. Return JSON only with keys fit_score, fit_confidence, fit_reason, recommendation, remote_status, remote_label, remote_confidence, remote_reason, highlight. highlight must be a concise technical Opportunity summary grounded only in the actual JD. Prefer about 25-40 words and never exceed 50 words. Summarize the concrete technologies, subsystems, tools, architectures, protocols, specialist responsibilities, and work area that distinguish the role. Do not add generic candidate-fit commentary. Do not use generic recommendation prose such as highly relevant, actionable, strong match, clear opportunity, aligns with the candidate, or job posting provides. If the fit is adjacent or weak, say that plainly rather than inventing niche relevance. Do not leave highlight empty when there is usable role/JD text. Do not end with a generic label such as fit, good fit, or technical fit; state the concrete reason instead. Never infer the highlight from search-query wording, related-job widgets, or generic recommendation text. Do not copy a long JD passage or repeat the company name. "
        'fit_score is 0-100. recommendation must be Apply Now, Review, Information Only, Reject, or Unknown; use Reject only for genuine role/technical irrelevance or hard eligibility evidence, never because pay/company size/engagement is missing or non-preferred. remote_label must be at most two words, for example Fully remote, Remote, Hybrid, On-site, or Unknown. remote_confidence is 0-100.\n\n'
        'CANDIDATE PREFERENCES:\n'+json.dumps(preference_scope,ensure_ascii=False)+'\n\n'
        f'ROLE: {opportunity.title}\nCOMPANY: {opportunity.company}\nKNOWN LOCATION: {opportunity.country}\n\nCLEANED OPPORTUNITY TEXT:\n{text[:18000]}'
    )
    try:
        raw=str(generate(prompt,stage='first_filter',timeout=90,subject={'type':'opportunity','id':opportunity.pk,'label':f'{opportunity.company} — {opportunity.title}'}) or '').strip()
        fenced=re.search(r'```(?:json)?\s*(.*?)```',raw,re.S|re.I)
        payload=(fenced.group(1).strip() if fenced else raw)
        a=payload.find('{'); b=payload.rfind('}')
        if a<0 or b<=a: raise ValueError('Classifier did not return JSON.')
        row=json.loads(payload[a:b+1])
        try: fit=max(0,min(100,int(row.get('fit_score'))))
        except Exception: fit=int(opportunity.fit_score or facts.get('search_pre_score') or 50)
        status=str(row.get('remote_status') or 'unknown').strip().lower()
        if status not in {'fully_remote','remote','hybrid','onsite','unknown'}: status='unknown'
        default_label={'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}[status]
        label=' '.join(str(row.get('remote_label') or default_label).split())[:40] or default_label
        try: remote_conf=max(0,min(100,int(row.get('remote_confidence') or 0)))
        except Exception: remote_conf=0
        remote={
            'status':status,'label':label,'confidence':remote_conf,
            'reason':str(row.get('remote_reason') or '')[:1200],
            'source':'LLM classification',
        }
        try: fit_conf=max(0,min(100,int(row.get('fit_confidence') or row.get('confidence') or 0)))
        except Exception: fit_conf=0
        fit_classification={
            'score':fit,'confidence':fit_conf,'reason':str(row.get('fit_reason') or '')[:1600],
            'recommendation':str(row.get('recommendation') or 'Unknown')[:80],
            'source':'LLM classification',
        }
        facts['remote_classification']=remote
        facts['fit_classification']=fit_classification
        opportunity.extracted_facts=facts
        opportunity.fit_score=fit
        opportunity.remote_text=(label + ((' — '+remote['reason']) if remote['reason'] else ''))[:220]
        recommendation=fit_classification['recommendation'].lower()
        if opportunity.status not in ('rejected','applied','closed'):
            if recommendation=='apply now': opportunity.status='apply'
            elif recommendation=='review': opportunity.status='review'
            elif recommendation=='information only': opportunity.status='info'
            elif recommendation=='reject': opportunity.status='rejected'
            elif recommendation=='unknown' and opportunity.status=='new': opportunity.status='unknown'
        opportunity.recommendation_reason=fit_classification['reason'][:2000]
        candidate_highlight=normalize_ai_fit_summary(row.get('highlight'))
        opportunity.list_highlight=(candidate_highlight or derive_opportunity_highlight(opportunity,title=opportunity.title,description=text,facts=facts,remote_text=opportunity.remote_text))[:600]
        return {'ok':True,'fit':fit_classification,'remote':remote,'highlight':opportunity.list_highlight}
    except LocalAILaneBusy:
        raise
    except Exception as exc:
        facts['remote_classification']={'status':'unknown','label':'Unknown','confidence':0,'reason':'No model-based remote classification is currently available.','source':'LLM classification'}
        facts['fit_classification']={'score':int(opportunity.fit_score or facts.get('search_pre_score') or 0),'confidence':0,'reason':'Fit classifier was unavailable; existing discovery score was preserved.','recommendation':'Unknown','source':'LLM classification','error':str(exc)[:500]}
        opportunity.extracted_facts=facts
        opportunity.remote_text='Unknown'
        return {'ok':False,'error':str(exc)}

def enrich(opportunity, allow_ai=True):
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    result={'ok':True,'fetched':False,'ai':False,'bytes':0,'notes':[]}
    text=opportunity.description or opportunity.raw_search_snippet or ''
    facts=opportunity.extracted_facts or {}
    has_jobposting_schema=bool((facts.get('role_page_classification') or {}).get('positive_signals') and 'JobPosting structured data' in (facts.get('role_page_classification') or {}).get('positive_signals',[]))
    description_html=facts.get('description_html','')
    prefetched=bool(facts.get('page_prefetched'))
    if prefetched: result['fetched']=True

    if cfg.feature_page_fetch and not prefetched and opportunity.url.startswith(('http://','https://')):
        started=time.time(); raw=b''
        try:
            if 'facebook.com' in opportunity.url and cfg.feature_authenticated_social_fetch:
                fb,err=facebook_authenticated_fetch(opportunity.url)
                if fb:
                    text=fb.get('text','') or text; result['bytes']=int(fb.get('html_length',0)); result['fetched']=True
                else:
                    result['notes'].append(err)
            else:
                r=requests.get(opportunity.url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'},timeout=18,allow_redirects=True)
                r.raise_for_status(); raw=r.content; result['bytes']=len(raw); result['fetched']=True
                soup=BeautifulSoup(raw,'html.parser')
                for bad in soup(['script','style','noscript','svg','iframe','form']): bad.extract()
                content=soup.select_one('[class*=job-description], [id*=job-description], [class*=jobDescription], main, article') or soup.body
                if content:
                    description_html=str(content)[:90000]
                visible=structured_visible_text(content or soup)
                text=clean_visible_text(visible or text)[:45000]
                job=_extract_jsonld(BeautifulSoup(raw,'html.parser'))
                has_jobposting_schema=bool(job)
                if job:
                    dt=_parse_dt(job.get('datePosted'))
                    if dt:
                        opportunity.declared_posted_at=dt
                        OpportunityEvidence.objects.update_or_create(opportunity=opportunity,kind='page_date',defaults={'label':'Page-declared publication date','value':dt.isoformat(),'source_url':(opportunity.target_url or opportunity.url),'confidence':92})
                    org=job.get('hiringOrganization') or {}
                    if isinstance(org,dict) and org.get('name') and not opportunity.company: opportunity.company=str(org.get('name'))[:220]
                    desc=job.get('description')
                    if desc:
                        description_html=str(desc)[:90000]
                        text=structured_visible_text(BeautifulSoup(str(desc),'html.parser'))[:45000]
                    loc=job.get('jobLocation') or job.get('applicantLocationRequirements')
                    if loc: opportunity.extracted_facts['jobLocation']=loc
                    role_location=extract_role_location(text,loc)
                    if role_location:
                        opportunity.role_location=role_location[:240]
                        role_country=infer_country(opportunity.url,role_location,location_hint=loc,strict=True)
                        if role_country: opportunity.country=role_country[:120]
                if r.url:
                    opportunity.target_url=r.url
                    opportunity.url=r.url
                    opportunity.extracted_facts['resolved_url']=r.url
            UsageMetric.objects.create(category='scrape',provider=opportunity.source.name if opportunity.source else 'direct',stage='page_fetch',requests=1,pages=1,latency_ms=int((time.time()-started)*1000),bytes_downloaded=result['bytes'],metadata={'url':opportunity.url})
        except Exception as e:
            UsageMetric.objects.create(category='scrape',provider=opportunity.source.name if opportunity.source else 'direct',stage='page_fetch',requests=1,pages=1,errors=1,latency_ms=int((time.time()-started)*1000),bytes_downloaded=len(raw),metadata={'url':opportunity.url,'error':str(e)})
            result['notes'].append(f'Page fetch failed: {e}')

    opportunity.data_downloaded_bytes += result['bytes']
    opportunity.description=text[:45000]
    facts=opportunity.extracted_facts or {}
    if description_html: facts['description_html']=description_html
    if not opportunity.language_code:
        opportunity.language_code=detect_language(text)
    facts['language_code']=opportunity.language_code
    opportunity.extracted_facts=facts

    # Search-query overlap is not enough to create a normal Opportunity.  Require
    # evidence that the fetched page is actually an actionable role/engagement.
    # Relevant technical pages without hiring/application evidence belong in Hidden
    # Market, not the Opportunity list.
    role_gate=classify_role_page(
        opportunity.url, opportunity.title, text,
        has_jobposting_schema=has_jobposting_schema,
        is_pdf=bool(facts.get('is_pdf')),
    )
    facts=opportunity.extracted_facts or {}
    facts['role_page_classification']=role_gate
    opportunity.extracted_facts=facts
    result['role_gate']=role_gate
    if not role_gate['accepted']:
        # Do not auto-hide items already acted on by the user; this gate is aimed at
        # newly discovered/search-noise records.
        user_acted = opportunity.status in ('apply','review','draft','applied','closed') or hasattr(opportunity, 'application')
        if not user_acted:
            # Qualification is advisory once discovery has persisted the record. Do not
            # automatically suppress/recycle a Local GPU result after it has appeared in
            # the UI; late enrichment used to make rows vanish between refreshes. Retain
            # the row with an explicit rejected/review state so its ID and history stay
            # stable until the user deliberately removes it.
            opportunity.status='rejected'
            opportunity.suppressed=False
            opportunity.rejection_reason=(
                'Not an actionable role/engagement: ' + role_gate['reason']
            )[:2000]
            opportunity.recommendation_reason='Qualification flagged this page as non-role content; the record was retained for review.'
            opportunity.save()
            result['ok']=False
            result['filtered_non_role']=True
            return result

    # Fit and working arrangement are model classifications over the cleaned role text and
    # candidate preferences. Local AI Discovery uses this local/selected classifier;
    # Cloud-native discovery already returns these fields and therefore skips this block.
    if allow_ai and text:
        classified=_llm_fit_remote(opportunity,text,Profile.objects.get_or_create(pk=1)[0])
        result['ai']=bool(classified.get('ok'))
        if not classified.get('ok'):
            result['notes'].append('Fit/remote classifier unavailable: '+str(classified.get('error') or 'unknown error'))

    # Language remains visible metadata; it does not hard-code an adjustment into the LLM fit score.

    opportunity.title=clean_placeholder(opportunity.title,'Untitled opportunity')[:300]
    opportunity.company=clean_placeholder(opportunity.company)[:220]
    history=evaluate_company_history(opportunity,base_score=opportunity.fit_score)
    result['application_history']=history
    opportunity.save()
    return result
