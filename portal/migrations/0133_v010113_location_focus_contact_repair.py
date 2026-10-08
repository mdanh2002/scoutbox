from datetime import datetime

from django.db import migrations
from django.utils import timezone


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt=value
    else:
        try:
            dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        except Exception:
            return None
    if timezone.is_naive(dt):
        try: dt=timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception: pass
    return dt


def _repair_post_age(Opportunity):
    try:
        from portal.services.freshness import post_age_label_for_days
    except Exception:
        return {'error':'freshness helper unavailable'}
    now=timezone.now(); checked=changed=0
    for row in Opportunity.objects.order_by('pk').iterator(chunk_size=300):
        checked+=1
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        post=dict(facts.get('post_age') or {}) if isinstance(facts.get('post_age'),dict) else {}
        raw=str(post.get('raw') or '')
        if raw.strip().casefold()=='evergreen':
            label='Evergreen'
        else:
            dt=getattr(row,'declared_posted_at',None) or _parse_dt(post.get('exact_date')) or getattr(row,'estimated_first_seen',None)
            days=None
            if dt:
                try: days=max(0,int((now-dt).total_seconds()//86400))
                except Exception: days=None
            if days is None:
                try: days=max(0,int(post.get('age_days'))) if post.get('age_days') is not None else None
                except Exception: days=None
            if days is None:
                if str(getattr(row,'freshness_label','') or '').strip()=='~ 3 days':
                    label='< 3 days'
                else:
                    continue
            else:
                label=post_age_label_for_days(days)
                post['age_days']=days
        updates=[]
        if str(getattr(row,'freshness_label','') or '')!=label:
            row.freshness_label=label; updates.append('freshness_label')
        if post:
            if post.get('label')!=label:
                post['label']=label; facts=dict(facts); facts['post_age']=post; row.extracted_facts=facts; updates.append('extracted_facts')
        if updates:
            row.save(update_fields=list(dict.fromkeys(updates)))
            changed+=1
    return {'checked':checked,'changed':changed}


def _clear_worldwide_company_locations(CompanyLead, Contact):
    stats={'hidden_leads_checked':0,'hidden_leads_changed':0,'contacts_checked':0,'contacts_changed':0}
    bad={'worldwide','global','remote worldwide','anywhere'}
    for row in CompanyLead.objects.order_by('pk').iterator(chunk_size=300):
        stats['hidden_leads_checked']+=1
        updates=[]
        if str(getattr(row,'country','') or '').strip().casefold() in bad:
            row.country=''; updates.append('country')
        if hasattr(row,'locations'):
            vals=[]
            for item in (getattr(row,'locations',None) or []):
                label=str((item or {}).get('label') if isinstance(item,dict) else item).strip().casefold()
                code=str((item or {}).get('code') if isinstance(item,dict) else '').strip().casefold()
                if label in bad or code in bad:
                    continue
                vals.append(item)
            if vals != (getattr(row,'locations',None) or []):
                row.locations=vals; updates.append('locations')
        if updates:
            row.save(update_fields=list(dict.fromkeys(updates)))
            stats['hidden_leads_changed']+=1
    for row in Contact.objects.order_by('pk').iterator(chunk_size=300):
        stats['contacts_checked']+=1
        updates=[]
        if str(getattr(row,'company_country','') or getattr(row,'country','') or '').strip().casefold() in bad:
            if hasattr(row,'company_country'):
                row.company_country=''; updates.append('company_country')
            elif hasattr(row,'country'):
                row.country=''; updates.append('country')
        if hasattr(row,'company_locations'):
            vals=[]
            for item in (getattr(row,'company_locations',None) or []):
                label=str((item or {}).get('label') if isinstance(item,dict) else item).strip().casefold()
                code=str((item or {}).get('code') if isinstance(item,dict) else '').strip().casefold()
                if label in bad or code in bad:
                    continue
                vals.append(item)
            if vals != (getattr(row,'company_locations',None) or []):
                row.company_locations=vals; updates.append('company_locations')
        if updates:
            row.save(update_fields=list(dict.fromkeys(updates)))
            stats['contacts_changed']+=1
    return stats


def _repair_email_channel(Opportunity):
    stats={'checked':0,'changed':0}
    for row in Opportunity.objects.filter(channel='email',contact_email='').order_by('pk').iterator(chunk_size=300):
        stats['checked']+=1
        row.channel='website'
        facts=dict(row.extracted_facts or {}) if isinstance(row.extracted_facts,dict) else {}
        apply=facts.get('apply_via') if isinstance(facts.get('apply_via'),dict) else {}
        if apply:
            apply=dict(apply)
            apply['channel']='website'
            apply['reason']='0.10.113 normalized email channel because no concrete assignable email was stored.'
            facts['apply_via']=apply
            row.extracted_facts=facts
            row.save(update_fields=['channel','extracted_facts'])
        else:
            row.save(update_fields=['channel'])
        stats['changed']+=1
    return stats


def forwards(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    now=timezone.now()
    try:
        BackgroundJob.objects.filter(status__in=['queued','running'], label__icontains='Focus').update(status='stopped',message='Superseded by ScoutBox 0.10.113 independent Focus namespace rebuild',finished_at=now)
    except Exception:
        pass
    focus_results={}
    try:
        from portal.services.focus import repair_model_focus_taxonomy
        target=int(getattr(ps,'max_focus_groups',15) or 15)
        focus_results={
            'opportunities':repair_model_focus_taxonomy(Opportunity,target,rewrite=True),
            'hidden_leads':repair_model_focus_taxonomy(CompanyLead,target,rewrite=True),
            'address_book':repair_model_focus_taxonomy(Contact,target,rewrite=True),
        }
    except Exception as exc:
        focus_results={'error':str(exc)[:500]}
    age_results=_repair_post_age(Opportunity)
    worldwide_results=_clear_worldwide_company_locations(CompanyLead,Contact)
    email_results=_repair_email_channel(Opportunity)
    state=dict(getattr(ps,'focus_taxonomy_state',{}) or {})
    state['v010113_focus_rebuild']=focus_results
    state['v010113_post_age_repair']=age_results
    state['v010113_worldwide_company_location_repair']=worldwide_results
    state['v010113_email_channel_repair']=email_results
    state['independent_focus_namespaces']=True
    ps.focus_taxonomy_state=state
    ps.focus_taxonomy_version='0.10.113'
    ps.country_repair_version=''
    ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version','country_repair_version'])
    try:
        BackgroundJob.objects.create(kind='other',label='0.10.113 data repair',status='completed',progress=100,message='0.10.113 repaired location, Focus, post age and contact-channel data',started_at=now,finished_at=timezone.now(),result={'focus':focus_results,'post_age':age_results,'worldwide_company_locations':worldwide_results,'email_channels':email_results})
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies=[('portal','0132_v010112_source_fidelity_focus_age')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
