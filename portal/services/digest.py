from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta
from html import escape
import re
from urllib.parse import urlsplit

from django.db.models import Sum
from django.utils import timezone
from django.conf import settings
from django.urls import reverse

from portal.models import (
    AIProviderConfig, ApplicationStatusEvent, BackgroundJob, Campaign,
    CloudBudgetUsage, CompanyLead, Contact, Opportunity, PortalSettings, Profile, UsageMetric,
)
from portal.services.highlights import derive_opportunity_highlight, normalize_ai_fit_summary, concise_technical_summary, opportunity_specific_highlight
from portal.services.company_research import company_domain_for_entity

TOP_N = 20
SUBSECTION_N = 10
_PLATFORM_HOSTS = (
    'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','monster.com','simplyhired.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
)


def _fmt_dt(value):
    if not value: return ''
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M:%S')


def _fmt_date(value):
    if not value: return ''
    return timezone.localtime(value).strftime('%d/%m/%Y')


def _clean(value, limit=240):
    text=' '.join(str(value or '').split()).strip()
    if len(text)<=limit: return text
    clipped=text[:limit].rsplit(' ',1)[0].rstrip(' ,;:-')
    return (clipped or text[:limit]).rstrip()+'…'


def _pct(used, limit):
    return 0.0 if not limit else 100.0 * float(used or 0) / float(limit)


def _fmt_bytes(value):
    n=float(value or 0)
    units=('B','KB','MB','GB','TB')
    i=0
    while n>=1024 and i<len(units)-1:
        n/=1024.0; i+=1
    if i==0: return f'{int(n):,} {units[i]}'
    return f'{n:.1f} {units[i]}'


def _host(url):
    try: return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception: return ''


def _platform_url(url):
    host=_host(url)
    return any(host==x or host.endswith('.'+x) for x in _PLATFORM_HOSTS)


def _best_company_name(entity, fallback=''):
    raw=_clean(getattr(entity,'company',''),120)
    if raw and raw.casefold() not in {'unknown company','unknown','company not identified','not identified'}:
        return raw
    intel=getattr(entity,'company_intel',{}) or {}
    if isinstance(intel,dict):
        candidate=_clean(intel.get('company'),120)
        if candidate and candidate.casefold() not in {'unknown company','unknown','company not identified','not identified'}:
            return candidate
        for row in intel.get('facts') or []:
            if isinstance(row,dict) and str(row.get('label') or '').strip().casefold()=='company':
                candidate=_clean(row.get('value'),120)
                if candidate: return candidate
    # Legacy ATS records may have lost the employer column while retaining the original
    # JobPosting JSON-LD. hiringOrganization is a safe employer source; the page publisher
    # or ATS hostname is deliberately ignored.
    facts=getattr(entity,'extracted_facts',{}) or {}
    html=str(facts.get('description_html') or '') if isinstance(facts,dict) else ''
    if html:
        m=re.search(r'"hiringOrganization"\s*:\s*\{.{0,1800}?"name"\s*:\s*"([^"\\]{2,220})"',html,re.I|re.S)
        if m:
            candidate=_clean(m.group(1).replace('\\u0026','&'),120)
            if candidate: return candidate
    return fallback


def _scoutbox_url(route_name, pk, base_url=''):
    base=str(base_url or 'http://localhost:8989').strip().rstrip('/')
    try: path=reverse(route_name,args=[pk])
    except Exception: return ''
    return base+path


def _company_url(entity):
    # Only label a URL as Company when it resolves to the same company-domain
    # selector used by Company Research/domain-age logic. ATS/job-board hosts remain
    # source URLs and can never masquerade as the company homepage.
    domain=company_domain_for_entity(entity)
    return ('https://'+domain+'/') if domain else ''


def _role_url(entity):
    for name in ('target_url','url','source_url','search_url'):
        value=str(getattr(entity,name,'') or '').strip()
        if value.startswith(('http://','https://')): return value
    return ''


_EXTRACTION_LABEL_RE=re.compile(
    r'^(?:\[(?:APPLICATION|QUALIFICATIONS?|PAGE_TITLE|TITLE|DESCRIPTION|SUMMARY|REQUIREMENTS?|RESPONSIBILITIES?|ABOUT|COMPANY|ROLE|LOCATION|SKILLS?)\]\s*)+',
    re.I,
)
_INTERNAL_LEAD_RE=re.compile(
    r'^(?:retained\s+as\s+(?:a\s+)?company[- ]level\s+lead|company[- ]level\s+lead\s+retained)(?:\s*[·|:—-].*)?$',
    re.I,
)


def _digest_prose(value, limit=260):
    """Return readable source prose without internal extraction labels."""
    text=_clean(value,limit)
    if not text:
        return ''
    text=_EXTRACTION_LABEL_RE.sub('',text).strip(' \t·|:—-')
    return _clean(text,limit)


def _internal_lead_note(value):
    """True for workflow metadata that should never be rendered as lead prose."""
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return False
    low=text.casefold()
    return bool(_INTERNAL_LEAD_RE.match(text)) or low.startswith('relevant:') or low.startswith('retained as company-level lead')


def _opportunity_digest_summary(o):
    """Use the same grounded, concise summary used by the Opportunities list view."""
    summary=opportunity_specific_highlight(o)
    if not summary:
        summary=concise_technical_summary(getattr(o,'list_highlight',''))
    if not summary:
        summary=derive_opportunity_highlight(o)
    return _digest_prose(summary,320)


def _lead_excerpt(x):
    # Company summaries/evidence are useful; internal retention/relevance bookkeeping is not.
    # Keep match_summary last because older records sometimes stored workflow metadata there.
    for value in (x.summary,x.evidence,x.evidence_translation,x.match_summary):
        if _internal_lead_note(value):
            continue
        text=_digest_prose(value,260)
        if text and text.casefold()!='summary pending.':
            return text
    return ''


def _remote_info(o):
    facts=o.extracted_facts if isinstance(o.extracted_facts,dict) else {}
    row=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}
    status=str(row.get('status') or '').casefold()
    labels={'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site'}
    return status, labels.get(status,'')


def _post_age(o, now):
    label=str(o.freshness_label or '').strip()
    dt=o.declared_posted_at or o.estimated_first_seen
    days=None
    if dt:
        try: days=max(0,(now-dt).days)
        except Exception: days=None
    if label in {'Evergreen','Evergreen Post'}: return 'Evergreen',days
    if label: return label,days
    if days is None: return '',None
    return f'{days}d',days


def _company_info_quality(entity):
    intel=getattr(entity,'company_intel',{}) or {}
    if not isinstance(intel,dict): return 0.0
    facts=[x for x in (intel.get('facts') or []) if isinstance(x,dict) and str(x.get('value') or '').strip()]
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    try: confidence=max(0,min(100,int(intel.get('confidence') or 0)))
    except Exception: confidence=0
    completeness=min(1.0,(len(facts)/5.0)+(0.15 if structured.get('founded_year') or structured.get('domain_age_label') else 0)+(0.15 if structured.get('size_range') else 0))
    return min(10.0, 6.0*completeness + 4.0*(confidence/100.0))


def _opp_rank(o, now):
    status,_label=_remote_info(o)
    remote={'fully_remote':30,'remote':28,'hybrid':10,'onsite':-8}.get(status,2)
    fit=35.0*max(0,min(100,int(o.fit_score or 0)))/100.0
    _age_label,days=_post_age(o,now)
    if str(o.freshness_label or '') in {'Evergreen','Evergreen Post'}: freshness=16
    elif days is None: freshness=5
    elif days<=2: freshness=25
    elif days<=7: freshness=22
    elif days<=30: freshness=16
    elif days<=90: freshness=9
    elif days<=180: freshness=4
    else: freshness=0
    company=_company_info_quality(o)
    contact=2 if o.contact_email else (1 if _role_url(o) else 0)
    return remote+fit+freshness+company+contact


def _lead_rank(x, now):
    score=55.0*max(0,min(100,int(x.score or 0)))/100.0
    text=' '.join(str(v or '') for v in (x.summary,x.match_summary,x.evidence)).casefold()
    remote=12 if re.search(r'\b(?:fully\s+)?remote\b|\bdistributed\b|\bwork from anywhere\b',text) else 0
    company=20.0*(_company_info_quality(x)/10.0)
    contact=8 if x.contact_email else (4 if x.contact_url else 0)
    age_hours=max(0,(now-x.created_at).total_seconds()/3600.0)
    recency=max(0,5*(1-age_hours/24.0))
    return score+remote+company+contact+recency


def _error_signature(text):
    text=_clean(text,500).lower(); text=re.sub(r'https?://\S+','<url>',text); text=re.sub(r'\b\d+\b','<n>',text)
    return text[:220]


def _company_meta_signals(entity):
    intel=getattr(entity,'company_intel',{}) or {}
    if not isinstance(intel,dict):
        return []
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    by_label={}
    for fact in intel.get('facts') or []:
        if isinstance(fact,dict):
            label=_clean(fact.get('label'),80).casefold(); value=_clean(fact.get('value'),180)
            if label and value: by_label[label]=value
    values=[]
    def add(label,*candidates):
        for value in candidates:
            value=_clean(value,180)
            if value:
                values.append(f'{label} {value}'); return
    add('Employees:',structured.get('employee_count_or_range'),structured.get('size_range'),by_label.get('employees'),by_label.get('company size'),by_label.get('size / structure'))
    add('Company age:',structured.get('domain_age_label'),structured.get('age_range'),by_label.get('company age'))
    add('Company location:',structured.get('location'),by_label.get('location'),by_label.get('headquarters'))
    return values[:3]


def _remote_sort_rank(value):
    text=str(value or '').casefold()
    if 'fully remote' in text or 'remote-first' in text: return 4
    if re.search(r'\bremote\b',text): return 3
    if 'hybrid' in text: return 2
    if 'onsite' in text or 'on-site' in text: return 0
    return 1


def _opp_row(o, now, *, fallback=False, base_url=''):
    status,remote=_remote_info(o); age,_days=_post_age(o,now)
    facts=o.extracted_facts if isinstance(o.extracted_facts,dict) else {}
    fit_row=facts.get('fit_classification') if isinstance(facts.get('fit_classification'),dict) else {}
    fit_value=int(o.fit_score or 0) if int(o.fit_score or 0)>0 or int(fit_row.get('confidence') or 0)>0 else None
    summary=_opportunity_digest_summary(o)
    return {
        'kind':'opportunity',
        'company':_best_company_name(o,'Unknown company'), 'role':_clean(o.title or 'Opportunity',150),
        # Daily Digest mirrors the concise Opportunities-list summary instead of appending
        # raw fetched/JD text (which can contain extraction labels/navigation fragments).
        'highlight':summary, 'description':'',
        'remote':remote, 'age':age, 'fit':fit_value, 'url':_role_url(o),
        'company_url':_company_url(o), 'email':str(o.contact_email or '').strip(), 'score':_opp_rank(o,now),
        'scoutbox_url':_scoutbox_url('opportunity_detail',o.pk,base_url), 'fallback':bool(fallback),
        'discovered_at':getattr(o,'first_seen_by_portal',None),'company_signals':_company_meta_signals(o),
        '_remote_rank':{'fully_remote':4,'remote':3,'hybrid':2,'onsite':0}.get(status,1),
    }


def _lead_row(x, now, *, fallback=False, base_url=''):
    raw_focus=x.match_summary if x.match_summary and len(x.match_summary.split())<=18 else ''
    focus='' if _internal_lead_note(raw_focus) else _digest_prose(raw_focus,120)
    raw_highlight=x.summary or ('' if focus else x.match_summary)
    highlight_source='' if _internal_lead_note(raw_highlight) else _digest_prose(raw_highlight,180)
    state=x.ai_state if isinstance(getattr(x,'ai_state',None),dict) else {}
    rr=state.get('remote_classification') if isinstance(state.get('remote_classification'),dict) else {}
    status=str(rr.get('status') or '').casefold()
    remote_label=_clean(rr.get('label'),60) or {'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site'}.get(status,'')
    if not remote_label and re.search(r'\bremote\b|\bdistributed\b|\bwork from anywhere\b',_lead_excerpt(x).casefold()):
        remote_label='Remote signal'; status='remote'
    return {
        'kind':'lead',
        'company':_best_company_name(x,'Hidden Lead'), 'role':focus,
        'highlight':highlight_source, 'description':_lead_excerpt(x),
        'remote':remote_label, 'age':'', 'fit':(int(x.score or 0) if int(x.score or 0)>0 else None), 'url':_role_url(x), 'company_url':_company_url(x),
        'email':str(x.contact_email or '').strip(), 'contact_url':str(x.contact_url or '').strip(), 'score':_lead_rank(x,now),
        'scoutbox_url':_scoutbox_url('hidden_lead_detail',x.pk,base_url), 'fallback':bool(fallback),
        'discovered_at':getattr(x,'created_at',None),'company_signals':_company_meta_signals(x),
        '_remote_rank':{'fully_remote':4,'remote':3,'hybrid':2,'onsite':0}.get(status,_remote_sort_rank(remote_label)),
    }


def _contact_row(c, now, *, fallback=False, base_url=''):
    intel=c.company_intel if isinstance(getattr(c,'company_intel',None),dict) else {}
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    remote=_clean(structured.get('remote_label') or structured.get('remote') or structured.get('remote_status'),60)
    company=_clean(c.company,120) or _best_company_name(c,'')
    role=_clean(c.name or c.title or 'Contact',150)
    summary=_clean(c.company_summary,240)
    source=str(c.source_url or '').strip()
    company_url=_company_url(c)
    contact_url=source if source.startswith(('http://','https://')) and source!=company_url else ''
    return {
        'kind':'contact',
        'company':company,'role':role,'highlight':summary,'description':'',
        'remote':remote,'age':'','fit':None,'url':source,'company_url':company_url,'contact_url':contact_url,
        'email':str(c.email or '').strip(),'score':0,'scoutbox_url':'','fallback':bool(fallback),
        'discovered_at':getattr(c,'created_at',None),'company_signals':_company_meta_signals(c),
        '_remote_rank':_remote_sort_rank(remote),
    }


def _contact_values(row):
    values=[]; seen=set()
    for label,key in (('Email','email'),('Company','company_url'),('Contact','contact_url'),('Source','url')):
        value=str(row.get(key) or '').strip()
        norm=value.casefold().rstrip('/')
        if not value or norm in seen: continue
        seen.add(norm); values.append((label,value))
    return values


def _row_signals(row):
    signals=[]
    if row.get('remote'): signals.append(str(row['remote']))
    if row.get('age'): signals.append('Post age '+str(row['age']))
    signals.extend(str(x) for x in (row.get('company_signals') or []) if str(x or '').strip())
    return signals


def _text_rows(lines, rows, total, empty_message='No entries.'):
    if not rows:
        lines.append('- '+empty_message)
        return
    for i,row in enumerate(rows,1):
        if row.get('kind')=='contact':
            name=row.get('role') or 'Contact'
            company=(' — '+row['company']) if row.get('company') and row.get('company')!=name else ''
            lines.append(f'{i}. {name}{company}')
        else:
            role=(' — '+row['role']) if row.get('role') else ''
            lines.append(f'{i}. {row["company"]}{role}')
        if row.get('discovered_at'): lines.append('   Discovered: '+_fmt_dt(row['discovered_at']))
        if row.get('highlight'): lines.append('   Description: '+row['highlight'])
        if row.get('description') and row.get('description')!=row.get('highlight'): lines.append('   Detail: '+row['description'])
        for signal in _row_signals(row):
            lines.append('   - '+signal)
        if row.get('scoutbox_url'): lines.append('   ScoutBox: '+row['scoutbox_url'])
        for label,value in _contact_values(row): lines.append(f'   {label}: {value}')
    if total>len(rows): lines.append(f'   + {total-len(rows)} more entries in ScoutBox.')


def _text_category(lines, title, new_rows, new_total, recent_rows, recent_total):
    lines.extend(['',title,'NEW TODAY'])
    _text_rows(lines,new_rows,new_total,'No new items today.')
    lines.extend(['','RECENT (LAST 7 DAYS)'])
    _text_rows(lines,recent_rows,recent_total,'No earlier items in the last 7 days.')


def _html_rows_table(rows,total,empty_message):
    if not rows:
        return f'<div class="empty-digest">{escape(empty_message)}</div>'
    body=[]
    for row in rows:
        if row.get('kind')=='contact':
            name=row.get('role') or 'Contact'
            identity=f'<div class="contact-identity-line"><b class="contact-name">{escape(name)}</b>'
            if row.get('company') and row.get('company')!=name:
                identity+=f'<span class="contact-company-sep"> — </span><span class="contact-company-inline" title="{escape(row["company"], quote=True)}">{escape(row["company"])}</span>'
            identity+='</div>'
        else:
            identity=f'<b>{escape(row["company"])}</b>'
            if row.get('role'): identity+=f'<div class="role">{escape(row["role"])}</div>'
        if row.get('discovered_at'):
            identity+=f'<div class="discovered">Discovered {escape(_fmt_dt(row["discovered_at"]))}</div>'
        why=''
        if row.get('highlight'): why+=f'<div class="why">{escape(row["highlight"])}</div>'
        if row.get('description') and row.get('description')!=row.get('highlight'): why+=f'<div class="desc">{escape(row["description"])}</div>'
        sig=_row_signals(row)
        signals='<ul class="signals-list">'+''.join(f'<li>{escape(x)}</li>' for x in sig)+'</ul>' if sig else ''
        contacts=''
        if row.get('scoutbox_url'):
            contacts+=f'<div class="contact-line scoutbox-link"><span class="contact-label">ScoutBox:</span> <span class="url-text">{escape(row["scoutbox_url"])}</span></div>'
        contacts+=''.join(f'<div class="contact-line"><span class="contact-label">{escape(label)}:</span> <span class="url-text">{escape(value)}</span></div>' for label,value in _contact_values(row))
        body.append(f'<tr><td class="identity">{identity}</td><td>{why}{signals}</td><td class="contact">{contacts}</td></tr>')
    more=f'<div class="more">+ {total-len(rows)} more entries in ScoutBox.</div>' if total>len(rows) else ''
    return '<table class="digest-table"><thead><tr><th>Company</th><th>Description</th><th>URLs</th></tr></thead><tbody>'+''.join(body)+'</tbody></table>'+more


def _html_category(title,new_rows,new_total,recent_rows,recent_total):
    return (
        f'<section><h2>{escape(title)}</h2>'
        '<h3 class="digest-subheading">New today</h3>'
        +_html_rows_table(new_rows,new_total,'No new items today.')+
        '<h3 class="digest-subheading recent-subheading">Recent · last 7 days</h3>'
        +_html_rows_table(recent_rows,recent_total,'No earlier items in the last 7 days.')+
        '</section>'
    )


def _campaign_digest_rows():
    rows=[]
    qs=Campaign.objects.filter(deleted_at__isnull=True).order_by('name')
    for campaign in qs:
        rows.append({
            'campaign':_clean(campaign.name or 'Campaign',100),
            'created':_fmt_date(campaign.created_at),
        })
    return rows


def _candidate_digest_rows():
    profile=Profile.objects.get_or_create(pk=1)[0]
    defaults={
        'engagement':['full-time','part-time','contract','agency/consulting','one-time project','collaboration','unknown'],
        'company_size':['solo/very small','small','startup','medium','unknown'],
        'pay_preferences':[],
        'interview_notes':'Prefer 1-2 sessions; take-home acceptable; avoid LeetCode/live coding/psychometric tests and long forms.',
    }
    stored=profile.scope_json if isinstance(profile.scope_json,dict) else {}
    scope={**defaults,**stored}
    rows=[]
    def add(label,value):
        value=_clean(value,220)
        if value: rows.append((label,value))
    add('Candidate',profile.display_name or 'Configured profile')
    add('High priority',profile.high_priority_text)
    add('Medium priority',profile.medium_priority_text)
    locations=profile.operating_locations or ([profile.operating_location] if profile.operating_location else [])
    add('Locations',', '.join(str(x) for x in locations if str(x or '').strip()))
    engagement=scope.get('engagement') or []
    add('Engagement',', '.join(str(x).replace('agency/consulting','consulting').replace('one-time project','project') for x in engagement))
    sizes=scope.get('company_size') or []
    add('Company sizes',', '.join(str(x) for x in sizes))
    pay=[]
    for item in (scope.get('pay_preferences') or [])[:3]:
        if not isinstance(item,dict): continue
        amount=str(item.get('amount') or '').strip(); currency=str(item.get('currency') or '').strip(); period=str(item.get('period') or '').strip()
        if amount:
            pay.append(' '.join(x for x in (currency,amount,('/ '+period if period else '')) if x))
    add('Preferred pay','; '.join(pay))
    add('Hiring process',scope.get('interview_notes') or '')
    return rows


def _html_campaigns(rows):
    if not rows:
        return '<section><h2>Configured campaigns</h2><div class="empty-digest">No campaigns configured.</div></section>'
    items=[]
    for row in rows:
        items.append(f'<li><b>{escape(row["campaign"])}</b><div>Created {escape(row["created"])}</div></li>')
    return '<section><h2>Configured campaigns</h2><ul class="campaign-digest-list">'+''.join(items)+'</ul></section>'


def _resource_usage(start, now):
    agg=UsageMetric.objects.filter(at__gte=start,at__lte=now).aggregate(
        requests=Sum('requests'), tokens_in=Sum('tokens_in'), tokens_out=Sum('tokens_out'),
        pages=Sum('pages'), errors=Sum('errors'), bytes_downloaded=Sum('bytes_downloaded'),
    )
    return {k:int(v or 0) for k,v in agg.items()}


def _current_settings(ps):
    mode=ps.get_discovery_mode_display() if hasattr(ps,'get_discovery_mode_display') else ('Cloud Web Discovery' if ps.discovery_mode=='cloud_web' else 'Local AI Discovery')
    if ps.discovery_mode=='cloud_web':
        provider=(ps.cloud_web_provider or 'cloud provider not selected').strip()
        primary=(ps.cloud_web_primary_model or '').strip()
        ai=provider+(f' / {primary}' if primary else '')
    else:
        ollama=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
        model=(getattr(ollama,'default_model','') or '').strip() if ollama else ''
        ai='Ollama local'+(f' / {model}' if model else '') if ollama else 'Local AI route'
    return {
        'Discovery mode':mode,
        'AI route':ai,
        'Opportunity selectivity':ps.get_opportunity_selectivity_display() if hasattr(ps,'get_opportunity_selectivity_display') else str(ps.opportunity_selectivity or '').title(),
        'Lead selectivity':ps.get_lead_selectivity_display() if hasattr(ps,'get_lead_selectivity_display') else str(ps.lead_selectivity or '').title(),
        'Contact admission':ps.get_contact_selectivity_display() if hasattr(ps,'get_contact_selectivity_display') else str(ps.contact_selectivity or '').title(),
        'Background':'Paused' if ps.background_paused else 'Running',
        'Scan interval':f'{int(ps.scraper_interval_minutes or 0)} min',
    }


def _html_kv_section(title,rows,columns=3):
    """Render compact metric sections using an actual table for email-client compatibility.

    CSS grid is not consistently supported by Gmail/other mail clients and can collapse
    these metrics into a long one-item-per-line list. A real table keeps the section
    compact without relying on modern layout CSS.
    """
    rows=list(rows or [])
    columns=max(1,int(columns or 1))
    table_rows=[]
    width=max(1,100//columns)
    for offset in range(0,len(rows),columns):
        cells=[]
        for label,value in rows[offset:offset+columns]:
            cells.append(
                f'<td class="stat-cell" width="{width}%" style="width:{width}%;vertical-align:top;border:1px solid #edf1f4;padding:7px 9px">'
                '<span style="display:block;color:#71818c;font-size:10px;text-transform:uppercase">'+escape(str(label))+'</span>'
                '<b style="display:block;font-size:12px;margin-top:2px;overflow-wrap:anywhere">'+escape(str(value))+'</b></td>'
            )
        while len(cells)<columns:
            cells.append(f'<td class="stat-cell empty" width="{width}%" style="width:{width}%;border:1px solid transparent;padding:7px 9px">&nbsp;</td>')
        table_rows.append('<tr>'+''.join(cells)+'</tr>')
    body=''.join(table_rows) or '<tr><td class="stat-cell empty">&nbsp;</td></tr>'
    return f'<section><h2>{escape(title)}</h2><table class="stats-table" role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;table-layout:fixed"><tbody>{body}</tbody></table></section>'


def build_24h_digest(now=None, *, test=False):
    '''Build the daily digest: today's discoveries plus a compact seven-day review window.'''
    now=now or timezone.now()
    start=now-timedelta(hours=24)
    local_now=timezone.localtime(now)
    today_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)
    recent_start=now-timedelta(days=7)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    portal_root=str(ps.portal_root_url or 'http://localhost:8989').strip().rstrip('/') or 'http://localhost:8989'

    opportunity_today_qs=Opportunity.objects.filter(first_seen_by_portal__gte=today_start,first_seen_by_portal__lte=now,suppressed=False,user_deleted=False)
    opportunity_recent_qs=Opportunity.objects.filter(first_seen_by_portal__gte=recent_start,first_seen_by_portal__lt=today_start,suppressed=False,user_deleted=False)
    lead_today_qs=CompanyLead.objects.filter(created_at__gte=today_start,created_at__lte=now,user_deleted=False,deleted_at__isnull=True)
    lead_recent_qs=CompanyLead.objects.filter(created_at__gte=recent_start,created_at__lt=today_start,user_deleted=False,deleted_at__isnull=True)
    contact_today_qs=Contact.objects.filter(created_at__gte=today_start,created_at__lte=now,deleted_at__isnull=True)
    contact_recent_qs=Contact.objects.filter(created_at__gte=recent_start,created_at__lt=today_start,deleted_at__isnull=True)

    opportunity_total=opportunity_today_qs.count(); opportunity_recent_total=opportunity_recent_qs.count()
    lead_total=lead_today_qs.count(); lead_recent_total=lead_recent_qs.count()
    contact_total=contact_today_qs.count(); contact_recent_total=contact_recent_qs.count()

    def digest_key(row):
        stamp=row.get('discovered_at')
        try: ts=stamp.timestamp() if stamp else 0
        except Exception: ts=0
        return (int(row.get('_remote_rank') or 0),ts)

    opp_rows=sorted((_opp_row(o,now,base_url=portal_root) for o in list(opportunity_today_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]
    opp_recent_rows=sorted((_opp_row(o,now,base_url=portal_root) for o in list(opportunity_recent_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]
    lead_rows=sorted((_lead_row(x,now,base_url=portal_root) for x in list(lead_today_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]
    lead_recent_rows=sorted((_lead_row(x,now,base_url=portal_root) for x in list(lead_recent_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]
    contact_rows=sorted((_contact_row(c,now,base_url=portal_root) for c in list(contact_today_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]
    contact_recent_rows=sorted((_contact_row(c,now,base_url=portal_root) for c in list(contact_recent_qs[:2000])),key=digest_key,reverse=True)[:SUBSECTION_N]

    status_qs=ApplicationStatusEvent.objects.filter(at__gte=start,at__lte=now,application__deleted_at__isnull=True,application__opportunity__user_deleted=False)
    status_total=status_qs.count()
    status_events=list(status_qs.select_related('application__opportunity').order_by('-at')[:5])

    usage=_resource_usage(start,now)
    configured_campaign_count=Campaign.objects.filter(deleted_at__isnull=True).count()
    campaign_rows=_campaign_digest_rows()
    settings_snapshot=_current_settings(ps)
    candidate_rows=_candidate_digest_rows()

    # Cloud budgets are daily hard caps. The old "automatic runs" percentage mixed a
    # per-campaign limit with all campaign runs and could report meaningless values such
    # as 520%, so it is intentionally omitted from the digest.
    cloud=CloudBudgetUsage.objects.filter(day=timezone.localdate(now)).first() or type('Cloud',(),{'requests':0,'tokens_in':0,'tokens_out_reasoning':0,'page_recovery':0})()
    limit_items=[
        ('Cloud requests',cloud.requests,ps.cloud_daily_requests),
        ('Input tokens',cloud.tokens_in,ps.cloud_daily_input_tokens),
        ('Output + reasoning tokens',cloud.tokens_out_reasoning,ps.cloud_daily_output_tokens),
        ('Page recovery',cloud.page_recovery,ps.cloud_page_recovery_per_day),
    ]
    budget_rows=[(label,f'{int(used or 0):,} / {int(limit or 0):,} ({_pct(used,limit):.0f}%)') for label,used,limit in limit_items]

    title='ScoutBox Test Digest' if test else 'ScoutBox Daily Digest'
    local_send_date=local_now.strftime('%d %b %Y')
    def _count_phrase(count, singular, plural=None, prefix=''):
        label=singular if int(count)==1 else (plural or singular+'s')
        return f'{int(count):,} {prefix}{label}'
    subject=(
        f'[{local_send_date}] - Daily Digest ('
        f'{_count_phrase(opportunity_total,"opportunity","opportunities","new ")}, '
        f'{_count_phrase(lead_total,"lead","leads","new ")}, '
        f'{_count_phrase(contact_total,"contact","contacts")})'
    )
    summary=f'{opportunity_total} new opportunities today · {lead_total} new leads today · {contact_total} contacts today · {status_total} application changes (24h)'
    activity_rows=[
        ('New opportunities today',f'{opportunity_total:,}'),('New hidden leads today',f'{lead_total:,}'),('New contacts today',f'{contact_total:,}'),
        ('Recent opportunities (7d)',f'{opportunity_recent_total:,}'),('Recent hidden leads (7d)',f'{lead_recent_total:,}'),('Recent contacts (7d)',f'{contact_recent_total:,}'),
        ('Application changes (24h)',f'{status_total:,}'),('Configured campaigns',f'{configured_campaign_count:,}'),('Requests (24h)',f'{usage["requests"]:,}'),
        ('Input tokens (24h)',f'{usage["tokens_in"]:,}'),('Output tokens (24h)',f'{usage["tokens_out"]:,}'),('Page/search operations (24h)',f'{usage["pages"]:,}'),
        ('Downloaded (24h)',_fmt_bytes(usage['bytes_downloaded'])),('Errors recorded (24h)',f'{usage["errors"]:,}'),
    ]

    lines=[title,f'Generated {_fmt_dt(now)}',summary]
    lines.extend(['','ACTIVITY'])
    lines.extend(f'- {label}: {value}' for label,value in activity_rows)
    lines.extend(['','CURRENT SETTINGS'])
    lines.extend(f'- {label}: {value}' for label,value in settings_snapshot.items())
    lines.extend(['','CANDIDATE PROFILE & ENGAGEMENT PREFERENCES'])
    lines.extend(f'- {label}: {value}' for label,value in candidate_rows)
    lines.extend(["","TODAY'S CLOUD BUDGET"])
    lines.extend(f'- {label}: {value}' for label,value in budget_rows)
    _text_category(lines,'OPPORTUNITIES',opp_rows,opportunity_total,opp_recent_rows,opportunity_recent_total)
    _text_category(lines,'HIDDEN LEADS',lead_rows,lead_total,lead_recent_rows,lead_recent_total)
    _text_category(lines,'ADDRESS BOOK',contact_rows,contact_total,contact_recent_rows,contact_recent_total)
    lines.extend(['','CONFIGURED CAMPAIGNS'])
    if campaign_rows:
        for row in campaign_rows:
            lines.append(f'- {row["campaign"]} — Created {row["created"]}')
    else:
        lines.append('- No campaigns configured.')
    if status_events:
        lines.extend(['','APPLICATION CHANGES'])
        for ev in status_events:
            opp=ev.application.opportunity
            lines.append(f'- {_clean((opp.company+" — " if opp.company else "")+(opp.title or "Application"),150)}: {ev.old_status or "unknown"} → {ev.new_status or "unknown"}')

    css='''body{margin:0;background:#f4f7f9;color:#172431;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.4}.wrap{max-width:940px;margin:0 auto;padding:22px 12px}.card{background:#fff;border:1px solid #d9e2e8;border-radius:8px;overflow:hidden}header{padding:18px 20px;background:#10283b;color:#fff}h1{font-size:20px;margin:0 0 5px}.period{color:#bed0dc;font-size:12px}.summary{margin-top:10px;font-weight:700}section{padding:14px 18px;border-top:1px solid #e7edf1}h2{font-size:13px;margin:0 0 9px;color:#31536a;text-transform:uppercase;letter-spacing:.04em}.digest-subheading{font-size:12px;margin:11px 0 7px;color:#526774}.digest-subheading:first-of-type{margin-top:2px}.recent-subheading{padding-top:8px;border-top:1px solid #edf1f4}.stats-table{width:100%;border-collapse:collapse;table-layout:fixed}.stat-cell{width:33.333%;vertical-align:top;border:1px solid #edf1f4;padding:7px 9px}.stat-cell span{display:block;color:#71818c;font-size:10px;text-transform:uppercase}.stat-cell b{display:block;font-size:12px;margin-top:2px;overflow-wrap:anywhere}.stat-cell.empty{border-color:transparent}.digest-table{width:100%;border-collapse:collapse;table-layout:fixed}.digest-table th{font-size:11px;text-align:left;color:#667985;border-bottom:1px solid #dfe7ec;padding:6px}.digest-table td{vertical-align:top;padding:9px 6px;border-bottom:1px solid #edf1f4}.digest-table th:nth-child(1),.digest-table td:nth-child(1){width:24%}.digest-table th:nth-child(3),.digest-table td:nth-child(3){width:27%}.role{font-weight:600;margin-top:2px}.contact-identity-line{white-space:normal}.contact-name{font-weight:700}.contact-company-sep{color:#8a9aa5}.contact-company-inline{font-weight:400;color:#526774}.why{font-weight:400;color:#263e4e}.desc{color:#526774;margin-top:4px}.signals-list{font-size:11px;color:#71818c;margin:6px 0 0;padding-left:17px}.signals-list li{margin:2px 0}.contact{font-size:11px;overflow-wrap:anywhere}.contact-line{margin:0 0 4px}.contact-label{font-weight:700;color:#526774}.url-text{word-break:break-all;color:#172431}.more{font-size:12px;color:#71818c;margin-top:8px}.discovered,.empty-digest{font-size:11px;color:#8a6d3b;margin-top:4px}.scoutbox-link{font-weight:600;color:#245f85}.campaign-digest-list{margin:0;padding-left:19px}.campaign-digest-list li{margin:0 0 8px}.campaign-digest-list li div{font-size:12px;color:#607482;margin-top:1px}@media(max-width:680px){.stat-cell{font-size:11px;padding:6px 5px}.digest-table,.digest-table tbody,.digest-table tr,.digest-table td{display:block}.digest-table thead{display:none}.digest-table td{width:auto!important}.digest-table td.contact{padding-top:0}}'''
    sections=[
        _html_kv_section('Activity',activity_rows),
        _html_kv_section('Current settings',list(settings_snapshot.items())),
        _html_kv_section('Candidate profile & engagement preferences',candidate_rows,columns=2),
        _html_kv_section("Today's cloud budget",budget_rows),
        _html_category('Opportunities',opp_rows,opportunity_total,opp_recent_rows,opportunity_recent_total),
        _html_category('Hidden Leads',lead_rows,lead_total,lead_recent_rows,lead_recent_total),
        _html_category('Address Book',contact_rows,contact_total,contact_recent_rows,contact_recent_total),
        _html_campaigns(campaign_rows),
    ]
    if status_events:
        items=''.join(f'<li>{escape(_clean(((ev.application.opportunity.company+" — ") if ev.application.opportunity.company else "")+(ev.application.opportunity.title or "Application"),150))}: {escape(ev.old_status or "unknown")} → {escape(ev.new_status or "unknown")}</li>' for ev in status_events)
        sections.append('<section><h2>Application changes · last 24 hours</h2><ul>'+items+'</ul></section>')
    html='<!doctype html><html><head><meta charset="utf-8"><style>'+css+'</style></head><body><div class="wrap"><div class="card">'+f'<header><h1>{escape(title)}</h1><div class="period">Generated {escape(_fmt_dt(now))}</div><div class="summary">{escape(summary)}</div></header>'+''.join(sections)+'</div></div></body></html>'
    return {
        'subject':subject,'body':'\n'.join(lines).rstrip()+'\n','html_body':html,
        'period_start':start,'period_end':now,
        'counts':{
            'opportunities':opportunity_total,'leads':lead_total,'contacts':contact_total,
            'recent_opportunities':opportunity_recent_total,'recent_leads':lead_recent_total,'recent_contacts':contact_recent_total,
            'status_changes':status_total,
        },
    }
