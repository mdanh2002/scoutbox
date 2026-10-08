from django.db import migrations


def cleanup_legacy_cloud_sources(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    # Do not delete these rows: Opportunities/Leads may reference them as historical
    # discovery provenance. Mark them internal instead; Search Sources hides cloud_ai
    # rows and Local discovery planners explicitly exclude them.
    SearchSource.objects.filter(category__iexact='Cloud AI Discovery').update(
        source_type='cloud_ai', enabled=True
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0089_v01036_company_career_pages')]
    operations=[migrations.RunPython(cleanup_legacy_cloud_sources,noop)]
