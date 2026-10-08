from django.db import migrations
from django.utils import timezone
import re

LABEL_BLACKLIST_MIN_CHARS = 7
AGGREGATOR_BLACKLIST_DOMAINS = {
    'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com', 'monster.com',
    'simplyhired.com', 'jooble.org', 'careerjet.com', 'talent.com', 'jobrapido.com',
    'jobstreet.com', 'seek.com.au', 'jobsdb.com', 'dice.com', 'careerbuilder.com',
    'wellfound.com', 'angel.co', 'builtin.com', 'remoteok.com', 'weworkremotely.com',
    'remotive.com', 'himalayas.app', 'jobicy.com', 'flexjobs.com', 'otta.com',
    'cord.co', 'sitepoint.com', 'workatastartup.com', 'ycstartupjobs.com',
    'startup.jobs', 'startupjobs.com', 'levels.fyi', 'theorg.com',
    'workable.com', 'greenhouse.io', 'lever.co', 'ashbyhq.com', 'smartrecruiters.com',
    'bamboohr.com', 'recruitee.com', 'comeet.com', 'jobvite.com', 'teamtailor.com',
    'icims.com', 'myworkdayjobs.com', 'workdayjobs.com', 'successfactors.com',
    'personio.com', 'pinpointhq.com', 'trakstar.com', 'jazzhr.com', 'paylocity.com',
    'ultipro.com', 'ultipro.ca', 'oraclecloud.com', 'hirebridge.com', 'applytojob.com',
    'catsone.com', 'breezy.hr', 'rippling-ats.com', 'jobsoid.com', 'zohorecruit.com',
    'freshteam.com', 'talentreef.com',
}
LOOSE_SIGNALS = (
    'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'recruitee',
    'bamboohr', 'jobvite', 'teamtailor', 'icims', 'myworkdayjobs', 'workdayjobs',
    'successfactors', 'personio', 'pinpointhq', 'jazzhr', 'hirebridge', 'applytojob',
    'zohorecruit', 'freshteam', 'talentreef', 'himalayas', 'remoteok', 'wellfound',
    'linkedin', 'indeed', 'glassdoor', 'ziprecruiter', 'sitepoint',
)


def _norm(value):
    text=str(value or '').strip().lower()
    if '://' in text:
        text=text.split('://', 1)[1]
    text=text.split('@')[-1].split(':')[0].strip('/').removeprefix('www.')
    return text[:255]


def _host(value):
    return _norm(value).split('/', 1)[0]


def _root(value):
    host=_host(value)
    parts=[p for p in host.split('.') if p]
    if len(parts) <= 2:
        return host
    two={'co.uk','org.uk','ac.uk','gov.uk','com.au','net.au','org.au','co.nz','com.sg','com.hk','com.br','com.mx','com.tr','co.jp','com.cn','com.tw','co.kr','co.in'}
    if '.'.join(parts[-2:]) in two and len(parts) >= 3:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _is_aggregator(value):
    host=_host(value)
    root=_root(value)
    if not host:
        return False
    for domain in AGGREGATOR_BLACKLIST_DOMAINS:
        d=_host(domain); rd=_root(d)
        if host == d or host.endswith('.' + d) or root == d or root == rd:
            return True
    compact=re.sub(r'[^a-z0-9]+', '', host)
    return any(signal in compact for signal in LOOSE_SIGNALS)


def _norm_label(value):
    return ' '.join(str(value or '').split()).casefold()[:255]


def _valid_company_label(label):
    text=' '.join(str(label or '').split()).strip()
    if len(_norm_label(text)) < LABEL_BLACKLIST_MIN_CHARS or len(text) > 80:
        return False
    noisy=('http://','https://','www.',' applicants',' applicant','posted ',' posted',' ago','job closed','closed job','hiring now','apply now','채용공고','지원자','개월 전','에서 이 자리')
    return not any(token in text.lower() for token in noisy)


def _row_urls(row):
    for field in ('target_url','canonical_url','url','search_url'):
        value=str(getattr(row, field, '') or '').strip().lower()
        if value:
            yield value


def _url_matches_domain(url, domain):
    needle=_host(domain)
    return bool(needle and needle in str(url or '').lower())


def retire_aggregator_blacklist_rows(apps, schema_editor):
    SourceBlacklist=apps.get_model('portal','SourceBlacklist')
    Opportunity=apps.get_model('portal','Opportunity')
    now=timezone.now()
    bad_domains=set()
    converted=[]
    for row in SourceBlacklist.objects.filter(deleted_at__isnull=True,built_in=False).order_by('created_at','id'):
        domain=_norm(getattr(row,'domain','') or '')
        if not domain or not _is_aggregator(domain):
            continue
        bad_domains.add(domain)
        label=' '.join(str(getattr(row,'label','') or '').split()).strip()[:255]
        if _valid_company_label(label):
            key=_norm_label(label)
            existing=None
            for maybe in SourceBlacklist.objects.filter(domain='',deleted_at__isnull=True).only('id','label'):
                if _norm_label(maybe.label)==key:
                    existing=maybe
                    break
            if existing is None:
                SourceBlacklist.objects.create(domain='',label=label,reason=f'Converted from aggregator-domain blacklist during v0.10.88 upgrade: {domain}',scope='all',enabled=True,built_in=False,deleted_at=None)
            else:
                SourceBlacklist.objects.filter(pk=existing.pk).update(enabled=True,deleted_at=None,reason=f'Converted from aggregator-domain blacklist during v0.10.88 upgrade: {domain}',scope='all')
            converted.append(label)
        SourceBlacklist.objects.filter(pk=row.pk).update(enabled=False,deleted_at=now,reason=((getattr(row,'reason','') or 'User blacklist')[:430] + ' | Recycled by v0.10.88: aggregator/job-board domains are never blacklisted.'))

    if bad_domains:
        reasons={f'Blocked by blacklist: {domain}' for domain in bad_domains}
        for opp in Opportunity.objects.filter(user_deleted=False,suppressed=True,rejection_reason__in=reasons).iterator():
            if any(_url_matches_domain(url, domain) for url in _row_urls(opp) for domain in bad_domains):
                Opportunity.objects.filter(pk=opp.pk,user_deleted=False).update(suppressed=False,is_read=False,rejection_reason='',updated_at=now)

    keys={_norm_label(label): label for label in converted if _valid_company_label(label)}
    if keys:
        for opp in Opportunity.objects.filter(user_deleted=False,suppressed=False).only('id','company').iterator():
            label=keys.get(_norm_label(getattr(opp,'company','') or ''))
            if label:
                Opportunity.objects.filter(pk=opp.pk,user_deleted=False,suppressed=False).update(suppressed=True,is_read=True,rejection_reason=f'Blocked by blacklist: {label}',updated_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0112_v01086_blacklist_aggregator_recovery'),
    ]
    operations = [
        migrations.RunPython(retire_aggregator_blacklist_rows, migrations.RunPython.noop),
    ]
