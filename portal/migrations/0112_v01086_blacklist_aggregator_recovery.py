from django.db import migrations

# Migration: 0112_v01086_blacklist_aggregator_recovery
from django.utils import timezone

LABEL_BLACKLIST_MIN_CHARS = 7
AGGREGATOR_BLACKLIST_DOMAINS = {
    'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com', 'monster.com',
    'simplyhired.com', 'jooble.org', 'careerjet.com', 'talent.com', 'jobrapido.com',
    'jobstreet.com', 'seek.com.au', 'jobsdb.com', 'dice.com', 'careerbuilder.com',
    'wellfound.com', 'builtin.com', 'remoteok.com', 'weworkremotely.com',
    'remotive.com', 'himalayas.app', 'jobicy.com', 'flexjobs.com', 'otta.com',
    'cord.co', 'workable.com', 'greenhouse.io', 'lever.co', 'ashbyhq.com',
    'smartrecruiters.com', 'bamboohr.com', 'recruitee.com', 'comeet.com',
    'jobs.lever.co', 'boards.greenhouse.io', 'apply.workable.com', 'jobs.ashbyhq.com',
}


def _norm(value):
    return str(value or '').strip().lower().removeprefix('www.').strip('/')[:255]


def _host(value):
    return _norm(value).split('/', 1)[0]


def _is_aggregator(value):
    host = _host(value)
    if not host:
        return False
    for domain in AGGREGATOR_BLACKLIST_DOMAINS:
        d = _host(domain)
        if host == d or host.endswith('.' + d):
            return True
    return False


def _norm_label(value):
    return ' '.join(str(value or '').split()).casefold()[:255]


def _valid_company_label(label):
    text = ' '.join(str(label or '').split()).strip()
    if len(_norm_label(text)) < LABEL_BLACKLIST_MIN_CHARS:
        return False
    # Old aggregator-domain rows sometimes stored an entire result-card/title blob
    # as the label.  Convert plausible company names, but avoid creating noisy
    # exact-match rules for long snippets.
    if len(text) > 80:
        return False
    noisy_tokens = (
        'http://', 'https://', 'www.', '\n', '\r', ' applicants', ' applicant',
        'posted ', ' posted', ' ago', 'job closed', 'closed job', 'hiring now', 'apply now',
        '채용공고', '지원자', '개월 전', '에서 이 자리',
    )
    key = text.lower()
    if any(token in key for token in noisy_tokens):
        return False
    return True


def _row_urls(row):
    for field in ('target_url', 'canonical_url', 'url', 'search_url'):
        value = str(getattr(row, field, '') or '').strip().lower()
        if value:
            yield value


def _url_matches_domain(url, domain):
    needle = _host(domain)
    if not needle:
        return False
    text = str(url or '').lower()
    return (needle in text)


def recover_aggregator_blacklist_rows(apps, schema_editor):
    SourceBlacklist = apps.get_model('portal', 'SourceBlacklist')
    Opportunity = apps.get_model('portal', 'Opportunity')
    now = timezone.now()
    bad_domains = set()
    converted_labels = []

    candidates = SourceBlacklist.objects.filter(
        deleted_at__isnull=True,
        built_in=False,
        scope__in=['all', 'opportunities'],
    ).filter(reason__icontains='Added from Opportunit')

    for row in candidates.order_by('created_at', 'id'):
        domain = _norm(getattr(row, 'domain', '') or '')
        if not domain or not _is_aggregator(domain):
            continue
        bad_domains.add(domain)
        label = ' '.join(str(getattr(row, 'label', '') or '').split()).strip()[:255]
        if _valid_company_label(label):
            label_key = _norm_label(label)
            existing = None
            for maybe in SourceBlacklist.objects.filter(domain='', deleted_at__isnull=True).only('id', 'label'):
                if _norm_label(maybe.label) == label_key:
                    existing = maybe
                    break
            if existing is None:
                SourceBlacklist.objects.create(
                    domain='',
                    label=label,
                    reason=f'Converted from aggregator-domain blacklist during v0.10.86 upgrade: {domain}',
                    scope=getattr(row, 'scope', 'all') or 'all',
                    enabled=True,
                    built_in=False,
                    deleted_at=None,
                )
            else:
                SourceBlacklist.objects.filter(pk=existing.pk).update(
                    enabled=True,
                    deleted_at=None,
                    reason=f'Converted from aggregator-domain blacklist during v0.10.86 upgrade: {domain}',
                    scope=getattr(row, 'scope', 'all') or 'all',
                )
            converted_labels.append(label)
        SourceBlacklist.objects.filter(pk=row.pk).update(
            enabled=False,
            deleted_at=now,
            reason=((getattr(row, 'reason', '') or 'Added from Opportunities')[:430] + ' | Recycled by v0.10.86: aggregator domains are never blacklisted for Opportunities.'),
        )

    if bad_domains:
        reasons = {f'Blocked by blacklist: {domain}' for domain in bad_domains}
        for opp in Opportunity.objects.filter(user_deleted=False, suppressed=True, rejection_reason__in=reasons).iterator():
            if any(_url_matches_domain(url, domain) for url in _row_urls(opp) for domain in bad_domains):
                Opportunity.objects.filter(pk=opp.pk, user_deleted=False).update(
                    suppressed=False,
                    is_read=False,
                    rejection_reason='',
                    updated_at=now,
                )

    # Keep the companies the user explicitly blacklisted blocked by exact company
    # name after conversion.  This is intentionally exact and case-insensitive-ish
    # in Python so we do not suppress unrelated companies with partial names.
    label_keys = {_norm_label(label): label for label in converted_labels if _valid_company_label(label)}
    if label_keys:
        for opp in Opportunity.objects.filter(user_deleted=False, suppressed=False).only('id', 'company').iterator():
            label = label_keys.get(_norm_label(getattr(opp, 'company', '') or ''))
            if label:
                Opportunity.objects.filter(pk=opp.pk, user_deleted=False, suppressed=False).update(
                    suppressed=True,
                    is_read=True,
                    rejection_reason=f'Blocked by blacklist: {label}',
                    updated_at=now,
                )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0111_v01085_stalled_local_ai_recovery'),
    ]

    operations = [
        migrations.RunPython(recover_aggregator_blacklist_rows, migrations.RunPython.noop),
    ]
