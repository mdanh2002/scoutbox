from django.db import migrations, models


LEGACY_BUILTIN_CAMPAIGNS = [
    'Embedded Remote by Region',
    'Reverse Engineering',
    'Retro / Legacy Systems',
    'Technical Writing',
    'Remote Teaching / Training',
]

LEAD_ONLY_DEFAULTS = [
    ('amazon.com', 'Amazon', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('microsoft.com', 'Microsoft', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('google.com', 'Google', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('apple.com', 'Apple', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('meta.com', 'Meta', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('nvidia.com', 'NVIDIA', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('intel.com', 'Intel', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('oracle.com', 'Oracle', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('ibm.com', 'IBM', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('cisco.com', 'Cisco', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('qualcomm.com', 'Qualcomm', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('samsung.com', 'Samsung', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('broadcom.com', 'Broadcom', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('amd.com', 'AMD', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('dell.com', 'Dell', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
    ('hp.com', 'HP', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.'),
]


def forwards(apps, schema_editor):
    SourceBlacklist = apps.get_model('portal', 'SourceBlacklist')
    SearchSource = apps.get_model('portal', 'SearchSource')
    Campaign = apps.get_model('portal', 'Campaign')

    # Existing blacklist behaviour must remain unchanged after adding scope.
    SourceBlacklist.objects.exclude(scope__in=['all', 'opportunities', 'hidden_leads']).update(scope='all')
    SourceBlacklist.objects.filter(scope='').update(scope='all')

    for domain, label, reason in LEAD_ONLY_DEFAULTS:
        row, created = SourceBlacklist.objects.get_or_create(
            domain=domain,
            defaults={'label': label, 'reason': reason, 'scope': 'hidden_leads', 'enabled': True, 'built_in': True},
        )
        if created:
            continue
        # Never silently broaden a user's existing custom block. Only shipped/built-in
        # rows are converted to the lead-only default.
        if row.built_in:
            row.label = label
            row.reason = reason
            row.scope = 'hidden_leads'
            row.enabled = True
            row.save(update_fields=['label', 'reason', 'scope', 'enabled'])

    # Old generic campaigns/templates are no longer shipped. Keep the resume-first
    # automatic campaign and every user-created campaign.
    Campaign.objects.filter(name__in=LEGACY_BUILTIN_CAMPAIGNS).delete()

    # Repair provider configuration defensively. The credential slots are preserved;
    # only an invalid/blank selected access mode is normalized.
    allowed = {
        'Yandex': {'public', 'yandex_api_key', 'yandex_iam'},
        'Baidu': {'public', 'baidu_qianfan'},
        'Naver': {'public', 'naver_legacy', 'naver_hub'},
    }
    for name, values in allowed.items():
        for source in SearchSource.objects.filter(name=name):
            cfg = dict(source.config_json or {})
            if str(cfg.get('access_type') or '').strip() not in values:
                cfg['access_type'] = 'public'
                source.config_json = cfg
                source.save(update_fields=['config_json'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0022_v0825_provider_campaign_outreach_fixes')]
    operations = [
        migrations.AddField(
            model_name='sourceblacklist',
            name='scope',
            field=models.CharField(
                choices=[('all', 'All Discovery'), ('opportunities', 'Opportunities Only'), ('hidden_leads', 'Hidden Leads Only')],
                default='all',
                max_length=24,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
