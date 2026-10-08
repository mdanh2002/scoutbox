from django.db import migrations, models


def _norm_url(value):
    import re
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    raw=str(value or '').strip()
    if not raw:
        return ''
    try:
        p=urlsplit(raw); host=(p.hostname or '').lower()
        if host.startswith('www.'):
            host=host[4:]
        path=re.sub(r'[-_]+','-',p.path or '/').rstrip('/') or '/'
        query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
               if not k.lower().startswith(('utm_','ref','trk','tracking','source'))]
        return urlunsplit(('https',host,path.lower(),urlencode(query),''))
    except Exception:
        return re.sub(r'[-_]+','-',raw.lower().rstrip('/'))


def _domain(value):
    from urllib.parse import urlsplit
    raw=str(value or '').strip()
    if not raw:
        return ''
    if '@' in raw and '://' not in raw:
        raw='https://'+raw.rsplit('@',1)[1]
    if '://' not in raw:
        raw='https://'+raw
    try:
        host=(urlsplit(raw).hostname or '').lower()
    except Exception:
        return ''
    if host.startswith('www.'):
        host=host[4:]
    parts=[x for x in host.split('.') if x]
    if len(parts)>=3 and parts[-2:] in (['co','uk'],['com','au'],['co','jp'],['com','sg']):
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:]) if len(parts)>=2 else host


def _company(value):
    import re
    text=' '.join(str(value or '').split()).casefold()
    text=re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co)\b\.?',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def _title(value):
    import re
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9+#]+',' ',str(value or '').casefold())).strip()


def _contact_org_key(contact):
    common={'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','icloud.com','me.com','yahoo.com','proton.me','protonmail.com'}
    email_domain=_domain(getattr(contact,'email',''))
    source_domain=_domain(getattr(contact,'source_url',''))
    domain=source_domain or email_domain
    if domain and domain not in common:
        return 'd:'+domain
    ck=_company(getattr(contact,'company',''))
    return ('c:'+ck) if ck else (('d:'+domain) if domain else '')


def _contact_score(contact):
    import re
    email=str(getattr(contact,'email','') or '').strip().lower()
    local=email.split('@',1)[0] if '@' in email else ''
    compact=re.sub(r'[^a-z0-9]+','',local)
    if any(compact.startswith(x) for x in ('recruit','talent','hiring','people','hr')):
        base=300
    elif any(compact.startswith(x) for x in ('jobs','job','careers','career')):
        base=220
    elif any(compact.startswith(x) for x in ('info','hello','contact','office','team','support','admin')):
        base=120
    else:
        base=400
    name=' '.join(str(getattr(contact,'name','') or '').split()).casefold()
    company=' '.join(str(getattr(contact,'company','') or '').split()).casefold()
    if name and name not in {'contact','unknown','n/a','none'} and name != company:
        base+=35
    if str(getattr(contact,'title','') or '').strip():
        base+=15
    base+=min(20,max(0,int(getattr(contact,'confidence',0) or 0))//5)
    return base


def _post_age_label(row, now):
    label=' '.join(str(getattr(row,'freshness_label','') or '').split()).strip()
    low=label.casefold()
    if low in {'evergreen','ever-green'}:
        return 'Evergreen'
    facts=getattr(row,'extracted_facts',{}) or {}
    post_age=facts.get('post_age') if isinstance(facts,dict) else {}
    if isinstance(post_age,dict) and post_age.get('evergreen'):
        return 'Evergreen'
    dt=getattr(row,'estimated_first_seen',None) or getattr(row,'declared_posted_at',None)
    if not dt:
        return 'Older / uncertain'
    try:
        days=max(0,(now-dt).days)
    except Exception:
        return 'Older / uncertain'
    if days < 10: return '~1 week'
    if days < 22: return '~2 weeks'
    if days < 46: return '~1 month'
    if days < 76: return '~2 months'
    if days < 107: return '~3 months'
    if days < 137: return '~4 months'
    if days < 168: return '~5 months'
    if days < 199: return '~6 months'
    return 'Older / uncertain'


def upgrade_0877_data(apps, schema_editor):
    from django.utils import timezone
    PortalSettings=apps.get_model('portal','PortalSettings')
    Contact=apps.get_model('portal','Contact')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Application=apps.get_model('portal','Application')

    # Change only values that exactly match the previous shipped defaults; deliberate
    # user overrides remain untouched.
    PortalSettings.objects.filter(cloud_web_searches_per_run=120).update(cloud_web_searches_per_run=100)
    PortalSettings.objects.filter(cloud_discovery_candidates_per_run=250).update(cloud_discovery_candidates_per_run=50)
    PortalSettings.objects.filter(cloud_daily_requests=1200).update(cloud_daily_requests=2000)
    PortalSettings.objects.filter(cloud_daily_output_tokens=750000).update(cloud_daily_output_tokens=2000000)
    # 0.8.76 changed these schema defaults but did not overwrite an already-created
    # singleton settings row. Upgrade the exact prior shipped values so an existing
    # installation actually receives the requested limits while preserving custom values.
    PortalSettings.objects.filter(cloud_page_recovery_per_day=50).update(cloud_page_recovery_per_day=500)
    PortalSettings.objects.filter(cloud_deep_research_candidates_per_run=30).update(cloud_deep_research_candidates_per_run=250)

    Contact.objects.filter(company_summary__in=['-','–','—']).update(company_summary='')

    # One-time 0.8.77 Address Book consolidation. Keep one active, best-quality contact
    # for each organization and move the rest to the Recycle Bin rather than deleting
    # history. A named personal mailbox outranks recruiting, which outranks jobs/careers,
    # which outranks generic info/contact addresses.
    now=timezone.now()
    groups={}
    for row in Contact.objects.filter(deleted_at__isnull=True).iterator(chunk_size=200):
        key=_contact_org_key(row)
        if key:
            groups.setdefault(key,[]).append(row)
    for rows in groups.values():
        if len(rows)<2:
            continue
        rows.sort(key=lambda r:(_contact_score(r),getattr(r,'last_seen',None) or getattr(r,'created_at',None),r.pk),reverse=True)
        keeper=rows[0]
        victim_ids=[r.pk for r in rows[1:]]
        Contact.objects.filter(pk__in=victim_ids,deleted_at__isnull=True).update(deleted_at=now,is_read=True)

    # Normalize visible Post Age buckets. Provider/method/source strings that leaked into
    # freshness_label are replaced by a human age range derived from stored evidence.
    allowed={'Evergreen','~1 week','~2 weeks','~1 month','~2 months','~3 months','~4 months','~5 months','~6 months','Older / uncertain'}
    for row in Opportunity.objects.filter(user_deleted=False,suppressed=False).only('pk','freshness_label','estimated_first_seen','declared_posted_at','extracted_facts').iterator(chunk_size=200):
        wanted=_post_age_label(row,now)
        if row.freshness_label not in allowed or row.freshness_label != wanted:
            Opportunity.objects.filter(pk=row.pk).update(freshness_label=wanted)

    # Re-run conservative visible-list reconciliation on upgrade so older databases get
    # the same no-duplicate behavior as new 0.8.77 persistence paths.
    rows=list(Opportunity.objects.filter(user_deleted=False,suppressed=False))
    app_ids=set(Application.objects.filter(deleted_at__isnull=True).values_list('opportunity_id',flat=True))
    rows.sort(key=lambda o:(o.pk in app_ids,int(o.fit_score or 0),o.last_seen or o.first_seen_by_portal,o.pk),reverse=True)
    seen_url={}; seen_role={}
    for row in rows:
        url=row.target_url or row.canonical_url or row.url or row.search_url
        nu=_norm_url(url); ck=_company(row.company); tk=_title(row.title); rk=(ck,tk) if ck and tk else None
        keeper=seen_url.get(nu) if nu else None
        if not keeper and rk:
            candidate=seen_role.get(rk)
            if candidate:
                a=getattr(candidate,'first_seen_by_portal',None); b=getattr(row,'first_seen_by_portal',None)
                if not a or not b or abs((a-b).days)<=180:
                    keeper=candidate
        if keeper:
            try:
                keeper.campaigns.add(*list(row.campaigns.all()))
            except Exception:
                pass
            Opportunity.objects.filter(pk=row.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)
        else:
            if nu: seen_url[nu]=row
            if rk: seen_role[rk]=row

    active=list(Opportunity.objects.filter(user_deleted=False,suppressed=False).exclude(status='rejected'))
    opp_domains=set(); opp_companies=set()
    for row in active:
        url=row.target_url or row.canonical_url or row.url or row.search_url
        dk=_domain(url); ck=_company(row.company)
        if dk: opp_domains.add(dk)
        if ck: opp_companies.add(ck)
    for lead in CompanyLead.objects.filter(user_deleted=False):
        url=lead.target_url or lead.source_url or lead.search_url
        dk=_domain(url); ck=_company(lead.company)
        if (dk and dk in opp_domains) or (ck and ck in opp_companies):
            CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)

    leads=list(CompanyLead.objects.filter(user_deleted=False))
    leads.sort(key=lambda x:(int(x.score or 0),x.updated_at or x.created_at,x.pk),reverse=True)
    seen_d={}; seen_c={}
    for lead in leads:
        url=lead.target_url or lead.source_url or lead.search_url; dk=_domain(url); ck=_company(lead.company)
        keeper=(seen_d.get(dk) if dk else None) or (seen_c.get(ck) if ck else None)
        if keeper:
            try:
                keeper.campaigns.add(*list(lead.campaigns.all()))
            except Exception:
                pass
            CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)
        else:
            if dk: seen_d[dk]=lead
            if ck: seen_c[ck]=lead


class Migration(migrations.Migration):
    dependencies=[('portal','0042_v0876_quality_and_url_health')]
    operations=[
        migrations.AlterField(model_name='portalsettings',name='cloud_web_searches_per_run',field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings',name='cloud_discovery_candidates_per_run',field=models.PositiveIntegerField(default=50)),
        migrations.AlterField(model_name='portalsettings',name='cloud_daily_requests',field=models.PositiveIntegerField(default=2000)),
        migrations.AlterField(model_name='portalsettings',name='cloud_daily_output_tokens',field=models.PositiveIntegerField(default=2000000)),
        migrations.RunPython(upgrade_0877_data,migrations.RunPython.noop),
    ]
