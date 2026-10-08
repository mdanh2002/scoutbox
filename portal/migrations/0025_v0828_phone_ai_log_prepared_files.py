from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def normalize_provider_access(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    allowed={
        'Yandex':{'public','yandex_api_key','yandex_iam'},
        'Baidu':{'public','baidu_qianfan'},
        'Naver':{'public','naver_legacy','naver_hub'},
    }
    for row in SearchSource.objects.filter(name__in=allowed):
        cfg=dict(row.config_json or {})
        selected=str(cfg.get('access_type') or '').strip()
        if selected not in allowed[row.name]:
            cfg['access_type']='public'
            row.config_json=cfg
            row.save(update_fields=['config_json'])



def enable_existing_facebook_pages(apps, schema_editor):
    # v0.8.28 removes the per-row Use toggle. Presence in Pages to Watch now
    # means the page is active; deleting the row is how users stop watching it.
    FacebookPage=apps.get_model('portal','FacebookPage')
    FacebookPage.objects.filter(enabled=False).update(enabled=True)


class Migration(migrations.Migration):
    dependencies = [('portal', '0024_v0827_application_files_and_blacklist_label')]

    operations = [
        migrations.AddField(
            model_name='profile', name='phone_number',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='companylead', name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hidden_leads', to='portal.searchsource'),
        ),
        migrations.CreateModel(
            name='AIRequestLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('provider', models.CharField(blank=True, max_length=80)),
                ('model', models.CharField(blank=True, max_length=200)),
                ('stage', models.CharField(blank=True, db_index=True, max_length=120)),
                ('runtime', models.CharField(blank=True, db_index=True, help_text='local or cloud', max_length=20)),
                ('subject_type', models.CharField(blank=True, db_index=True, max_length=60)),
                ('subject_id', models.CharField(blank=True, max_length=120)),
                ('subject_label', models.CharField(blank=True, max_length=300)),
                ('input_text', models.TextField(blank=True)),
                ('output_text', models.TextField(blank=True)),
                ('attachments', models.JSONField(blank=True, default=list)),
                ('tokens_in', models.PositiveIntegerField(default=0)),
                ('tokens_out', models.PositiveIntegerField(default=0)),
                ('ok', models.BooleanField(default=True)),
                ('error', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={'ordering': ['-at']},
        ),
        migrations.RunPython(normalize_provider_access,migrations.RunPython.noop),
        migrations.RunPython(enable_existing_facebook_pages,migrations.RunPython.noop),
        migrations.CreateModel(
            name='PreparedApplicationFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_kind', models.CharField(choices=[('cv', 'Resume'), ('cover', 'Cover Letter')], max_length=20)),
                ('file_format', models.CharField(blank=True, max_length=20)),
                ('label', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='generated/%Y/%m/')),
                ('source_asset_label', models.CharField(blank=True, max_length=255)),
                ('selected_for_email', models.BooleanField(default=False)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prepared_files', to='portal.application')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
