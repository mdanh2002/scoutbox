from urllib.parse import urlsplit

from django.db import migrations
from django.utils import timezone


def _normalize_pattern(value):
    raw=(value or '').strip().lower()
    if not raw:
        return ''
    if '://' in raw:
        parsed=urlsplit(raw)
        raw=(parsed.netloc+parsed.path).strip('/')
    return raw.removeprefix('www.').strip().strip('/')[:255]


def _url_key(url):
    try:
        parsed=urlsplit(url or '')
        host=(parsed.netloc or '').lower().removeprefix('www.')
        path=(parsed.path or '').lower().strip('/')
        return host+(('/'+path) if path else '')
    except Exception:
        return ''


def _matches(pattern, url):
    pat=_normalize_pattern(pattern)
    key=_url_key(url)
    if not pat or not key:
        return False
    if '/' in pat:
        return key == pat or key.startswith(pat.rstrip('/') + '/')
    host=key.split('/',1)[0]
    return host == pat or host.endswith('.'+pat)


def _scope_matches(row_scope, requested_scope):
    row_scope=(row_scope or 'all').strip() or 'all'
    requested_scope=(requested_scope or 'all').strip() or 'all'
    return row_scope == 'all' or requested_scope == 'all' or row_scope == requested_scope


def enforce_existing_blacklist(apps, schema_editor):
    SourceBlacklist=apps.get_model('portal','SourceBlacklist')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')

    rules=[(row.domain,row.scope) for row in SourceBlacklist.objects.filter(enabled=True,deleted_at__isnull=True).only('domain','scope')]
    if not rules:
        return

    def blocked(urls,scope):
        for url in urls:
            if not url:
                continue
            for pattern,row_scope in rules:
                if _scope_matches(row_scope,scope) and _matches(pattern,url):
                    return pattern
        return ''

    now=timezone.now()
    for row in Opportunity.objects.filter(suppressed=False,user_deleted=False).iterator(chunk_size=250):
        pattern=blocked((row.target_url,row.canonical_url,row.url,row.search_url),'opportunities')
        if not pattern:
            continue
        Opportunity.objects.filter(pk=row.pk,suppressed=False,user_deleted=False).update(
            suppressed=True,
            is_read=True,
            rejection_reason=f'Blocked by blacklist: {pattern}'[:1000],
            updated_at=now,
        )

    for row in CompanyLead.objects.filter(user_deleted=False).iterator(chunk_size=250):
        pattern=blocked((row.target_url,row.source_url,row.search_url),'hidden_leads')
        if not pattern:
            continue
        CompanyLead.objects.filter(pk=row.pk,user_deleted=False).update(
            user_deleted=True,
            deleted_at=now,
            is_read=True,
            updated_at=now,
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0045_v0879_chatbot_output_default')]
    operations=[migrations.RunPython(enforce_existing_blacklist,migrations.RunPython.noop)]
