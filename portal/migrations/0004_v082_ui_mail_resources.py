from django.db import migrations, models
import django.utils.timezone


def cleanup_legacy_placeholders(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    Contact=apps.get_model('portal','Contact')
    bad={'blank','unknown','n/a','na','none','null','not specified','not available','-','—'}
    for o in Opportunity.objects.all().iterator():
        fields=[]
        if (o.company or '').strip().lower() in bad:
            o.company=''; fields.append('company')
        if (o.title or '').strip().lower() in bad:
            # Keep the record useful without displaying a literal placeholder.
            o.title='Opportunity'; fields.append('title')
        if fields: o.save(update_fields=fields)
    for c in Contact.objects.all().iterator():
        local=(c.email or '').split('@',1)[0].lower().replace('-','').replace('_','').replace('.','')
        if 'noreply' in local or 'donotreply' in local or 'sales' in local:
            c.generic=True; c.save(update_fields=['generic'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0003_v081_search_and_lab')]
    operations = [
        migrations.AlterField(model_name='backgroundjob', name='kind', field=models.CharField(choices=[('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('hidden_scan','Hidden-market scan'),('cold_draft','Cold outreach draft'),('enrich','Opportunity enrichment'),('prepare','Application preparation'),('translate','Translation'),('company_research','Company research'),('performance','Performance test'),('other','Automatic task')], default='other', max_length=30)),
        migrations.AddField(model_name='mailevent', name='body_text', field=models.TextField(blank=True, help_text='Full plain-text body when ScoutBox generated or fetched the message.')),
        migrations.AddField(model_name='mailevent', name='body_html', field=models.TextField(blank=True, help_text='Full HTML body when available; rendered through a sanitizer.')),
        migrations.AddField(model_name='mailevent', name='delivery_status', field=models.CharField(blank=True, default='', help_text='SMTP/observation outcome such as sent, failed, observed.', max_length=30)),
        migrations.AddField(model_name='mailevent', name='delivery_error', field=models.TextField(blank=True)),
        migrations.AddField(model_name='companylead', name='evidence_translation', field=models.TextField(blank=True)),
        migrations.AddField(model_name='contact', name='source_url', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='portalsettings', name='background_state_changed_at', field=models.DateTimeField(default=django.utils.timezone.now)),
        migrations.CreateModel(
            name='ResourceSample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('at', models.DateTimeField(default=django.utils.timezone.now)),
                ('cpu_percent', models.FloatField(default=0)),
                ('memory_percent', models.FloatField(default=0)),
                ('memory_used_mb', models.PositiveIntegerField(default=0)),
                ('gpu_percent', models.FloatField(blank=True, null=True)),
                ('gpu_memory_percent', models.FloatField(blank=True, null=True)),
                ('gpu_label', models.CharField(blank=True, max_length=200)),
            ],
            options={'ordering': ['-at']},
        ),
        migrations.RunPython(cleanup_legacy_placeholders, noop_reverse),
    ]
