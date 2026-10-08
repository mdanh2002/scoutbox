
import re
import urllib.parse
from django.db import migrations

_ROLE=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')

def _bad(value):
    text=' '.join(str(value or '').split()).strip()
    if not text: return True
    if text[:1] in {'•','·','▪','-'}: return True
    if text.casefold().startswith(('responsibilities','requirements','develop new ','design and ','work hands-on ','collaborate with ','focusing on ')): return True
    return len(text)>115 and (text.endswith('.') or text.count(',')>=2)

def _from_sources(row):
    facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
    refresh=facts.get('manual_metadata_refresh') if isinstance(facts.get('manual_metadata_refresh'),dict) else {}
    company=' '.join(str(row.company or '').split()).strip()
    for src in refresh.get('sources') or []:
        if not isinstance(src,dict): continue
        title=' '.join(str(src.get('title') or '').split()).strip(' -–—|·:;')
        if not title or len(title)>180 or _bad(title) or not _ROLE.search(title): continue
        if company and title.casefold().startswith(company.casefold()):
            title=title[len(company):].lstrip(' -–—|:')
        else:
            parts=re.split(r'\s+(?:-|–|—|\|)\s+',title,maxsplit=1)
            if len(parts)==2 and not _ROLE.search(parts[0]) and _ROLE.search(parts[1]):
                title=parts[1].strip()
        if title and _ROLE.search(title): return title[:300]
    return ''

def _from_url(row):
    url=str(row.target_url or row.url or '')
    try: slug=urllib.parse.unquote(urllib.parse.urlsplit(url).path.rstrip('/').rsplit('/',1)[-1])
    except Exception: return ''
    if not slug or slug.isdigit(): return ''
    text=' '.join(x for x in re.split(r'[-_]+',slug) if x and not x.isdigit()).strip()
    if not _ROLE.search(text) or not (4<=len(text)<=120): return ''
    words=[]
    for word in text.split():
        low=word.lower()
        if low in {'rtos','fpga','ai','ml','qa','c','c++'}: words.append(word.upper())
        elif low in {'linux','ios'}: words.append(word.title())
        else: words.append(word.capitalize())
    return ' '.join(words)[:300]

def repair(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity'); SearchSource=apps.get_model('portal','SearchSource')
    naver_ids=set(SearchSource.objects.filter(name__iexact='Naver').values_list('pk',flat=True))
    if not naver_ids: return
    for row in Opportunity.objects.filter(source_id__in=naver_ids).iterator(chunk_size=250):
        if not _bad(row.title): continue
        candidate=_from_sources(row) or _from_url(row)
        if candidate and not _bad(candidate) and candidate!=row.title:
            Opportunity.objects.filter(pk=row.pk).update(title=candidate)

def noop(apps,schema_editor): pass

class Migration(migrations.Migration):
    dependencies=[('portal','0084_v01028_origin_campaign_naver_backfill')]
    operations=[migrations.RunPython(repair,noop)]
