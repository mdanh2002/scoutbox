from django.db import migrations


def add_company_career_pages(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    SearchSource.objects.update_or_create(
        name='Company career pages',
        defaults={
            'category':'ATS / hosted career pages',
            'source_type':'company_career_pages',
            'base_url':'',
            'enabled':True,
            'preferred_initial':False,
            'priority':65,
            'provider_weight':100,
            'low_value_marketplace':False,
            'requires_credentials':False,
            'adapter_status':'preset',
            'notes':'Local AI Discovery umbrella: configured search engines locate relevant companies, then search their own hiring/collaboration/project pages. Not used by Cloud Web Discovery.',
            'config_json':{'company_career_pages':True,'local_only':True},
            'public_fallback':False,
        },
    )


def remove_company_career_pages(apps, schema_editor):
    apps.get_model('portal','SearchSource').objects.filter(name='Company career pages').delete()


class Migration(migrations.Migration):
    dependencies=[('portal','0088_v01034_cloud_direct_source_routing')]
    operations=[migrations.RunPython(add_company_career_pages,remove_company_career_pages)]
