from django.db import migrations
from django.utils import timezone


def _truthy(value):
    return value is True or str(value or '').strip().lower() in {'1','true','yes','y','evergreen'}


def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    checked=changed=0
    for row in Opportunity.objects.order_by('pk').iterator(chunk_size=300):
        checked += 1
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        post=facts.get('post_age') if isinstance(facts.get('post_age'),dict) else {}
        label=str(row.freshness_label or '').strip()
        current_status=str(post.get('current_status') or facts.get('current_status') or '').strip().lower()
        try:
            evergreen_conf=int(post.get('evergreen_confidence') or post.get('confidence') or row.freshness_confidence or 0)
        except Exception:
            evergreen_conf=int(row.freshness_confidence or 0)
        evergreen=(
            label in {'Evergreen','Evergreen Post','Ever-green'} or
            _truthy(post.get('evergreen')) or
            str(post.get('post_age_class') or '').strip().lower()=='evergreen' or
            str(post.get('class') or '').strip().lower()=='evergreen'
        ) and evergreen_conf >= 60 and current_status not in {'closed','expired','filled','removed','inactive'}
        if evergreen and label != 'Evergreen':
            facts=dict(facts); post=dict(post)
            post['evergreen']=True
            post['post_age_class']='evergreen'
            post['label']='Evergreen'
            if evergreen_conf:
                post['evergreen_confidence']=evergreen_conf
            facts['post_age']=post
            row.extracted_facts=facts
            row.freshness_label='Evergreen'
            if not row.freshness_confidence:
                row.freshness_confidence=min(100,max(60,evergreen_conf or 60))
            row.save(update_fields=['extracted_facts','freshness_label','freshness_confidence','updated_at'])
            changed += 1
    try:
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        state=dict(ps.focus_taxonomy_state or {})
        state['v010114_evergreen_post_age_repair']={'checked':checked,'changed':changed}
        ps.focus_taxonomy_state=state
        ps.save(update_fields=['focus_taxonomy_state'])
    except Exception:
        pass
    try:
        BackgroundJob.objects.create(kind='other',label='0.10.114 Evergreen post-age repair',status='completed',progress=100,message='Restored Evergreen as a visible Post Age value where retained evidence classifies the opportunity as evergreen',started_at=timezone.now(),finished_at=timezone.now(),result={'checked':checked,'changed':changed})
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies=[('portal','0134_v010114_source_location_worldwide_toolbar')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
