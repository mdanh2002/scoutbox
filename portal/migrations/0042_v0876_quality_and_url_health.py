from django.db import migrations, models


def _norm_url(value):
    import re
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    raw=str(value or '').strip()
    if not raw: return ''
    try:
        p=urlsplit(raw); host=(p.hostname or '').lower()
        if host.startswith('www.'): host=host[4:]
        path=re.sub(r'[-_]+','-',p.path or '/').rstrip('/') or '/'
        query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith(('utm_','ref','trk','tracking','source'))]
        return urlunsplit(('https',host,path.lower(),urlencode(query),''))
    except Exception:
        return re.sub(r'[-_]+','-',raw.lower().rstrip('/'))


def _domain(value):
    from urllib.parse import urlsplit
    raw=str(value or '').strip()
    if not raw: return ''
    if '@' in raw and '://' not in raw: raw='https://'+raw.split('@',1)[1]
    if '://' not in raw: raw='https://'+raw
    try:
        host=(urlsplit(raw).hostname or '').lower()
    except Exception:
        return ''
    if host.startswith('www.'): host=host[4:]
    parts=[x for x in host.split('.') if x]
    if len(parts)>=3 and parts[-2:] in (['co','uk'],['com','au'],['co','jp'],['com','sg']): return '.'.join(parts[-3:])
    return '.'.join(parts[-2:]) if len(parts)>=2 else host


def _company(value):
    import re
    text=' '.join(str(value or '').split()).casefold()
    text=re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co)\b\.?',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def _title(value):
    import re
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9+#]+',' ',str(value or '').casefold())).strip()


def clean_existing(apps, schema_editor):
    from django.utils import timezone
    Contact=apps.get_model('portal','Contact')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Application=apps.get_model('portal','Application')
    Contact.objects.filter(company_summary__in=['-','–','—']).update(company_summary='')
    Contact.objects.filter(company__iexact='Implicitconversions').update(company='Implicit Conversions')
    for value in ['Remote worldwide','Worldwide','Global','Anywhere','Remote','Distributed']:
        Contact.objects.filter(company_country__iexact=value).update(company_country='')
        Opportunity.objects.filter(country__iexact=value).update(country='')
        CompanyLead.objects.filter(country__iexact=value).update(country='')

    # Upgrade cleanup is intentionally conservative: same normalized role URL or the
    # same company + role title is one Opportunity. Prefer rows with an Application,
    # then better fit/newer evidence, and preserve campaign membership on the keeper.
    now=timezone.now(); rows=list(Opportunity.objects.filter(user_deleted=False,suppressed=False))
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
                if not a or not b or abs((a-b).days) <= 180:
                    keeper=candidate
        if keeper:
            try: keeper.campaigns.add(*list(row.campaigns.all()))
            except Exception: pass
            Opportunity.objects.filter(pk=row.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)
        else:
            if nu: seen_url[nu]=row
            if rk: seen_role[rk]=row

    active=list(Opportunity.objects.filter(user_deleted=False,suppressed=False).exclude(status='rejected'))
    opp_domains=set(); opp_companies=set()
    for row in active:
        url=row.target_url or row.canonical_url or row.url or row.search_url
        if _domain(url): opp_domains.add(_domain(url))
        if _company(row.company): opp_companies.add(_company(row.company))

    # A concrete Opportunity owns the organization on active review surfaces.
    for lead in CompanyLead.objects.filter(user_deleted=False):
        url=lead.target_url or lead.source_url or lead.search_url
        if (_domain(url) and _domain(url) in opp_domains) or (_company(lead.company) and _company(lead.company) in opp_companies):
            CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)

    # Hidden Leads are company-centric; retain the strongest/newest active row per org.
    leads=list(CompanyLead.objects.filter(user_deleted=False))
    leads.sort(key=lambda x:(int(x.score or 0),x.updated_at or x.created_at,x.pk),reverse=True)
    seen_d={}; seen_c={}
    for lead in leads:
        url=lead.target_url or lead.source_url or lead.search_url; dk=_domain(url); ck=_company(lead.company)
        keeper=(seen_d.get(dk) if dk else None) or (seen_c.get(ck) if ck else None)
        if keeper:
            try: keeper.campaigns.add(*list(lead.campaigns.all()))
            except Exception: pass
            CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True)
        else:
            if dk: seen_d[dk]=lead
            if ck: seen_c[ck]=lead


class Migration(migrations.Migration):
    dependencies=[('portal','0041_v0874_cloud_selection_contacts_lead_status')]
    operations=[
        migrations.AddField(model_name='opportunity',name='target_http_status',field=models.PositiveSmallIntegerField(blank=True,help_text='Most recent direct HTTP status observed for the final opportunity URL.',null=True)),
        migrations.AddField(model_name='opportunity',name='target_checked_at',field=models.DateTimeField(blank=True,help_text='When the final opportunity URL was last checked directly.',null=True)),
        migrations.AddField(model_name='opportunity',name='target_check_error',field=models.CharField(blank=True,default='',help_text='Most recent final opportunity URL check error, if any.',max_length=500)),
        migrations.AlterField(model_name='portalsettings',name='cloud_discovery_candidates_per_run',field=models.PositiveIntegerField(default=250)),
        migrations.AlterField(model_name='portalsettings',name='cloud_deep_research_candidates_per_run',field=models.PositiveIntegerField(default=250)),
        migrations.AlterField(model_name='portalsettings',name='cloud_page_recovery_per_day',field=models.PositiveIntegerField(default=500)),
        migrations.RunPython(clean_existing,migrations.RunPython.noop),
    ]
