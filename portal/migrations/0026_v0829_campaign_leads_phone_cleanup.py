from django.db import migrations, models


def clean_imported_placeholders(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    Application=apps.get_model('portal','Application')
    # Historical imports are existing history, not new inbox-style work. Older releases
    # created them with Application.is_read=False, which made the navigation badge equal
    # the size of an imported archive rather than the number of unseen application items.
    for opp in Opportunity.objects.all().iterator():
        facts=dict(opp.extracted_facts or {})
        imported=bool(
            str(opp.url or '').startswith('https://imported.invalid/')
            or facts.get('imported_status') is not None
            or facts.get('import_inference_method')
            or facts.get('synthetic_url')
        )
        if not imported:
            continue
        changed=[]
        if opp.canonical_url and 'imported.invalid' in opp.canonical_url:
            opp.canonical_url=''; changed.append('canonical_url')
        if opp.target_url and 'imported.invalid' in opp.target_url:
            opp.target_url=''; changed.append('target_url')
        if str(opp.url or '').startswith('https://imported.invalid/') and not facts.get('synthetic_url'):
            facts['synthetic_url']=True; opp.extracted_facts=facts; changed.append('extracted_facts')
        if changed:
            opp.save(update_fields=changed)
        Application.objects.filter(opportunity_id=opp.pk).update(is_read=True)


class Migration(migrations.Migration):
    dependencies=[('portal','0025_v0828_phone_ai_log_prepared_files')]
    operations=[
        migrations.AlterField(model_name='profile',name='phone_number',field=models.CharField(blank=True,max_length=32)),
        migrations.AddField(model_name='companylead',name='campaigns',field=models.ManyToManyField(blank=True,related_name='leads',to='portal.campaign')),
        migrations.RunPython(clean_imported_placeholders,migrations.RunPython.noop),
    ]
