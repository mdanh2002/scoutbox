from django.db import migrations, models
import portal.models

DEFAULT_ADDITIONAL_LANGUAGES=['French','German','Spanish']


def forward(apps,schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    for cfg in PortalSettings.objects.all():
        changed=[]
        # 0.11.74's Auto mode had no stored extra-language defaults. Seed the new
        # supplementary list once; an explicitly Custom/empty configuration stays empty.
        if (cfg.multilingual_language_mode or 'auto')=='auto' and not (cfg.multilingual_languages or []):
            cfg.multilingual_languages=list(DEFAULT_ADDITIONAL_LANGUAGES)
            changed.append('multilingual_languages')
        if cfg.multilingual_language_mode!='auto':
            cfg.multilingual_language_mode='auto'
            changed.append('multilingual_language_mode')
        if changed:
            cfg.save(update_fields=changed)


def backward(apps,schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0153_v01174_discovery_markets_domain_neutral')]
    operations=[
        migrations.AlterField(
            model_name='portalsettings',
            name='multilingual_languages',
            field=models.JSONField(blank=True,default=portal.models.default_multilingual_languages),
        ),
        migrations.RunPython(forward,backward),
    ]
