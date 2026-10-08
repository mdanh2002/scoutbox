from datetime import datetime

from django.db import migrations
from django.utils import timezone


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt=value
    else:
        raw=str(value).strip().replace('Z','+00:00')
        try:
            dt=datetime.fromisoformat(raw)
        except Exception:
            return None
    if timezone.is_naive(dt):
        try:
            dt=timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            pass
    return dt


def _normalize_post_ages(Opportunity):
    try:
        from portal.services.freshness import post_age_label_for_days
    except Exception:
        return {'checked': 0, 'changed': 0, 'error': 'freshness helper unavailable'}
    now=timezone.now()
    checked=changed=0
    for row in Opportunity.objects.order_by('pk').iterator(chunk_size=300):
        checked += 1
        facts=row.extracted_facts if isinstance(row.extracted_facts, dict) else {}
        post_age=facts.get('post_age') if isinstance(facts.get('post_age'), dict) else {}
        raw=str(post_age.get('raw') or '')
        if raw.strip().casefold() == 'evergreen':
            label='Evergreen'
        else:
            dt=(getattr(row,'declared_posted_at',None) or
                _parse_dt(post_age.get('exact_date')) or
                getattr(row,'estimated_first_seen',None))
            days=None
            if dt:
                try:
                    days=max(0, int((now-dt).total_seconds()//86400))
                except Exception:
                    days=None
            if days is None:
                try:
                    days=max(0,int(post_age.get('age_days'))) if post_age.get('age_days') is not None else None
                except Exception:
                    days=None
            if days is None:
                continue
            label=post_age_label_for_days(days)
            post_age=dict(post_age)
            post_age['age_days']=days
        update=[]
        if str(getattr(row,'freshness_label','') or '') != label:
            row.freshness_label=label; update.append('freshness_label')
        if post_age:
            post_age=dict(post_age)
            if post_age.get('label') != label:
                post_age['label']=label
                facts=dict(facts); facts['post_age']=post_age
                row.extracted_facts=facts; update.append('extracted_facts')
        if update:
            row.save(update_fields=list(dict.fromkeys(update)))
            changed += 1
    return {'checked':checked,'changed':changed}


def forwards(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]

    # Older blank/full Focus jobs used campaign wording in the topic-rule text. Stop
    # their persisted job records before rebuilding from record content only.
    try:
        now=timezone.now()
        BackgroundJob.objects.filter(status__in=['queued','running'], label__icontains='Focus').update(
            status='stopped',
            message='Superseded by ScoutBox 0.10.112 source-faithful Focus rebuild',
            finished_at=now,
        )
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

    age_results=_normalize_post_ages(Opportunity)
    state=dict(getattr(ps,'focus_taxonomy_state',{}) or {})
    state['source_fidelity_release']='0.10.112'
    state['v010112_focus_rebuild']=focus_results
    state['v010112_post_age_repair']=age_results
    state['campaign_text_excluded_from_topic_rules']=True
    ps.focus_taxonomy_state=state
    ps.focus_taxonomy_version='0.10.112'
    # Force the normal post-upgrade grounded location repair to re-evaluate retained
    # records using the new recruiter-region precedence and extraction rules. Running
    # page/network repair inside a schema migration would make deployment brittle.
    ps.country_repair_version=''
    ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version','country_repair_version'])


class Migration(migrations.Migration):
    dependencies=[('portal','0131_v010111_multi_locations_source_spinner')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
