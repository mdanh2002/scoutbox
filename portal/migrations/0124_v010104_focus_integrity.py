from django.db import migrations, models
from django.utils import timezone


def adopt_existing_focus_taxonomy(apps, schema_editor):
    """Adopt a healthy existing taxonomy without clearing/repopulating it on upgrade.

    0.10.102 intentionally performed a one-time full Focus rebuild. 0.10.104 changes the
    lifecycle: established taxonomies become durable and only rare growth/age thresholds
    may trigger another full population. A schema migration never calls AI/network code.
    """
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    now=timezone.now().isoformat()
    model_specs=(
        ('opportunities',apps.get_model('portal','Opportunity')),
        ('hidden_leads',apps.get_model('portal','CompanyLead')),
        ('contacts',apps.get_model('portal','Contact')),
    )
    state={}
    healthy_all=True
    for key,model in model_specs:
        total=model.objects.count()
        classified=model.objects.exclude(focus='').exclude(focus='Unclassified').count()
        groups=model.objects.exclude(focus='').exclude(focus='Unclassified').values('focus').distinct().count()
        healthy=bool(total and groups and (total < 25 or classified >= max(5,int(total*0.20))))
        if healthy:
            state[key]={
                'last_full_population_at':now,
                'last_full_population_count':total,
                'last_classified_count':classified,
                'last_group_count':groups,
                'adopted_existing':True,
            }
        else:
            state[key]={
                'last_full_population_at':'',
                'last_full_population_count':total,
                'last_classified_count':classified,
                'last_group_count':groups,
                'adopted_existing':False,
            }
            healthy_all=False
    PortalSettings.objects.update(
        focus_taxonomy_state=state,
        focus_taxonomy_version=('0.10.104' if healthy_all else ''),
        integrity_repair_version='',
    )
    # Stop an obsolete queued 0.10.102 rebuild from wiping/reclassifying a taxonomy after
    # the 0.10.104 code is already active. Running jobs are deliberately left untouched.
    BackgroundJob.objects.filter(
        kind='other',label='Rebuild Focus taxonomy for 0.10.102',status='queued'
    ).update(status='stopped',message='Superseded by stable Focus taxonomy lifecycle in 0.10.104',finished_at=timezone.now())


class Migration(migrations.Migration):
    dependencies=[('portal','0123_v010103_country_location_repair')]
    operations=[
        migrations.AddField(
            model_name='portalsettings',name='focus_taxonomy_state',
            field=models.JSONField(blank=True,default=dict,help_text='Per-list Focus taxonomy population baselines and maintenance timestamps used to keep Focus labels stable between rare full rebuilds.'),
        ),
        migrations.AddField(
            model_name='portalsettings',name='integrity_repair_version',
            field=models.CharField(blank=True,default='',help_text='Last release whose blacklist/opportunity-integrity repair completed.',max_length=32),
        ),
        migrations.RunPython(adopt_existing_focus_taxonomy,migrations.RunPython.noop),
    ]
