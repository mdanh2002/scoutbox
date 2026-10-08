from django.db import migrations
import base64
import re
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

ENGINE_HOSTS={
    'google.com','www.google.com','bing.com','www.bing.com','duckduckgo.com','html.duckduckgo.com',
    'search.brave.com','search.yahoo.com','r.search.yahoo.com','startpage.com','www.startpage.com',
    'ecosia.org','www.ecosia.org','yandex.com','www.yandex.com','yandex.ru','www.yandex.ru',
    'baidu.com','www.baidu.com','search.naver.com','naver.com','www.naver.com','openapi.naver.com',
}


def host_of(value):
    try:
        return (urlsplit(str(value or '')).netloc or '').lower().split('@')[-1].split(':')[0]
    except Exception:
        return ''


def is_engine(value):
    host=host_of(value)
    return any(host==d or host.endswith('.'+d) for d in ENGINE_HOSTS)


def unwrap(value):
    raw=str(value or '').strip()
    if not raw.startswith(('http://','https://')):
        return raw
    try:
        p=urlsplit(raw); host=p.netloc.lower(); qs=parse_qs(p.query)
        for key in ('uddg','url','target','q','r'):
            cand=unquote((qs.get(key) or [''])[0] or '').strip()
            if cand.startswith(('http://','https://')) and not is_engine(cand):
                return cand
        if host.endswith('bing.com'):
            token=unquote((qs.get('u') or [''])[0] or '')
            if token.startswith('a1'):
                token=token[2:]
            if token:
                try:
                    cand=base64.urlsafe_b64decode(token+'='*((4-len(token)%4)%4)).decode('utf-8','ignore').strip()
                    if cand.startswith(('http://','https://')) and not is_engine(cand):
                        return cand
                except Exception:
                    pass
        if host.endswith('yahoo.com'):
            m=re.search(r'/RU=([^/]+)',p.path)
            if m:
                cand=unquote(m.group(1)).strip()
                if cand.startswith(('http://','https://')) and not is_engine(cand):
                    return cand
    except Exception:
        pass
    return raw


def canonical(value):
    try:
        p=urlsplit(str(value or '').strip())
        if not p.scheme or not p.netloc:
            return str(value or '')
        return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',p.query,''))[:1000]
    except Exception:
        return str(value or '')[:1000]


def forwards(apps,schema_editor):
    SourceBlacklist=apps.get_model('portal','SourceBlacklist')
    Lead=apps.get_model('portal','CompanyLead')
    Opportunity=apps.get_model('portal','Opportunity')

    for domain,label,reason in (
        ('arm.com','Arm','Vendor/community/support content is excluded from Market Studies lead discovery.'),
        ('kernel.org','Linux kernel project','Kernel project/reference content is not a commercial Market Studies lead.'),
    ):
        SourceBlacklist.objects.update_or_create(domain=domain,defaults={'label':label,'reason':reason,'enabled':True,'built_in':True})

    # Remove existing Market Studies rows from the newly built-in exclusions.
    for lead in Lead.objects.all().iterator():
        urls=(lead.target_url,lead.source_url,lead.search_url)
        if any(host_of(u).removeprefix('www.') in ('arm.com','kernel.org') or host_of(u).endswith(('.arm.com','.kernel.org')) for u in urls if u):
            lead.delete(); continue
        changed=[]
        for field in ('search_url','target_url','source_url'):
            old=getattr(lead,field,'') or ''; new=unwrap(old)
            if new!=old:
                setattr(lead,field,new[:1000]); changed.append(field)
        # If provider provenance still points at the engine but target is already real,
        # make both user-facing URLs point at the resolved website.
        if is_engine(lead.search_url) and lead.target_url and not is_engine(lead.target_url):
            lead.search_url=lead.target_url; changed.append('search_url')
        if changed:
            lead.save(update_fields=list(dict.fromkeys(changed)))

    for opp in Opportunity.objects.all().iterator():
        changed=[]
        for field in ('search_url','target_url','url'):
            old=getattr(opp,field,'') or ''; new=unwrap(old)
            if new!=old:
                setattr(opp,field,new[:1000]); changed.append(field)
        if is_engine(opp.search_url) and opp.target_url and not is_engine(opp.target_url):
            opp.search_url=opp.target_url; changed.append('search_url')
        if opp.target_url and not is_engine(opp.target_url):
            if not opp.url or is_engine(opp.url):
                opp.url=opp.target_url; changed.append('url')
            new_can=canonical(opp.target_url)
            if new_can and new_can!=opp.canonical_url:
                opp.canonical_url=new_can; changed.append('canonical_url')
        # Old unresolved engine links cannot be valid final opportunities.
        final=opp.target_url or opp.url
        if is_engine(final):
            opp.suppressed=True; opp.rejection_reason='Suppressed during v0.8.20 upgrade: final URL was an unresolved search-engine redirect.'; changed += ['suppressed','rejection_reason']
        # Clean the concrete false-positive pattern reported from Technical City.
        if host_of(final).removeprefix('www.')=='technical.city' and re.search(r'(?i)\b(comparisons?|reviews?|benchmarks?)\b',opp.title or ''):
            opp.suppressed=True; opp.rejection_reason='Editorial/comparison page; no actionable role evidence.'; changed += ['suppressed','rejection_reason']
        if changed:
            opp.save(update_fields=list(dict.fromkeys(changed)))


class Migration(migrations.Migration):
    dependencies=[('portal','0016_v0818_market_quality_ui_cleanup')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
