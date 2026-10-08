from django.db import migrations, models


def mark_focus_rebuild(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    # 0.10.102 deliberately regenerates Focus from record content through Local AI.
    # Network/AI work is never performed in a schema migration; the scheduler starts the
    # one-time background rebuild after services restart. Clearing the old labels ensures
    # slash-heavy 0.10.101 taxonomy cannot bias the new AI-generated vocabulary.
    Opportunity.objects.update(focus='')
    CompanyLead.objects.update(focus='')
    Contact.objects.update(focus='')
    PortalSettings.objects.update(focus_taxonomy_version='')


class Migration(migrations.Migration):
    dependencies=[('portal','0121_v010101_focus_facets')]
    operations=[
        migrations.AddField(
            model_name='portalsettings',
            name='focus_taxonomy_version',
            field=models.CharField(blank=True,default='',help_text='Last release whose AI-generated Focus taxonomy rebuild completed.',max_length=32),
        ),
        migrations.RunPython(mark_focus_rebuild,migrations.RunPython.noop),
    ]
