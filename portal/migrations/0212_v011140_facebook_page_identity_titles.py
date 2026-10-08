import re
from urllib.parse import unquote
from django.db import migrations

_SYSTEM_SLUGS={'facebook','reg','dating','android_upgrade','messenger','login','help','watch','marketplace','gaming','groups','events'}
_POST_TITLE_RE=re.compile(r'''(?ix)\b(
    are\s+you\s+looking|looking\s+for\s+(?:a\s+)?career|career\s+change|we(?:'re|\s+are)\s+hiring|
    now\s+hiring|join\s+(?:our|the)\s+team|current\s+open\s+positions?|apply\s+(?:now|today)|
    vacancy\s+(?:alert|announcement)|job\s+(?:alert|opening|opportunity)|hiring\s+(?:now|alert)
)\b''')
_REGION_SUFFIXES={'NA':'North America'}


def _page_id_display(page_id):
    raw=unquote(str(page_id or '')).strip().strip('/')
    if not raw or raw.casefold() in _SYSTEM_SLUGS or raw.isdigit():
        return ''
    text=re.sub(r'[_\-.]+',' ',raw)
    text=re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',text)
    text=re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])',' ',text)
    parts=[x for x in text.split() if x]
    if parts and parts[-1].upper() in _REGION_SUFFIXES:
        parts[-1]=_REGION_SUFFIXES[parts[-1].upper()]
    return ' '.join(parts).strip()[:300]


def _looks_like_post_title(value):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip()
    if not text:
        return False
    return bool(_POST_TITLE_RE.search(text) or ('?' in text and len(text)>45) or ('!' in text and len(text)>55))


def forwards(apps, schema_editor):
    FacebookPage=apps.get_model('portal','FacebookPage')
    AuditLog=apps.get_model('portal','AuditLog')
    repaired=0
    for row in FacebookPage.objects.all().iterator(chunk_size=250):
        if not _looks_like_post_title(row.page_title):
            continue
        replacement=_page_id_display(row.page_id)
        if not replacement or replacement.casefold()==str(row.page_title or '').strip().casefold():
            continue
        row.page_title=replacement
        reason='0.11.140 repaired a Facebook post/search-result title to the stable Page identity derived from the Page ID.'
        prior=' '.join(str(row.validation_reason or '').split()).strip()
        row.validation_reason=(reason + ((' Previous: '+prior) if prior else ''))[:500]
        row.save(update_fields=['page_title','validation_reason','updated_at'])
        repaired+=1

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.140').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.140',summary='ScoutBox upgraded to version 0.11.140.',
            metadata={'release':'0.11.140','facebook_page_identity_title_fix':True,'facebook_page_titles_repaired':repaired},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0211_v011139_company_identity_integrity')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
