from django.db import migrations, models


def forward(apps, schema_editor):
    AIRequestLog=apps.get_model('portal','AIRequestLog')
    AIRequestLog.objects.filter(ok=True,tokens_out__gt=0).update(status='completed')
    AIRequestLog.objects.exclude(ok=True,tokens_out__gt=0).update(status='failed')
    SearchSource=apps.get_model('portal','SearchSource')
    SearchSource.objects.filter(category__in=['Specialist / custom','Feeds / announcements']).delete()
    SearchSource.objects.filter(name='RSS / Atom feeds').delete()
    SearchSource.objects.filter(category='Europe / international').exclude(name='Welcome to the Jungle').delete()
    SearchSource.objects.filter(name='Welcome to the Jungle').update(category='Public community / social sources')


def backward(apps, schema_editor):
    # Removed built-in presets are recreated by older seed_defaults code if an operator
    # deliberately rolls the application back; user-created CustomSearchDomain rows are
    # unaffected by this migration.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0038_v0866_search_budgets_campaign_description')]
    operations=[
        migrations.AddField(
            model_name='airequestlog',name='status',
            field=models.CharField(choices=[('queued','Queued'),('running','Running'),('completed','Completed'),('failed','Failed')],db_index=True,default='completed',max_length=20),
        ),
        migrations.RunPython(forward,backward),
    ]
