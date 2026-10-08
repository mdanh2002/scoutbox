from django.db import migrations


def forwards(apps, schema_editor):
    SourceBlacklist = apps.get_model('portal', 'SourceBlacklist')
    TrackingSuffixReserve = apps.get_model('portal', 'TrackingSuffixReserve')
    AuditLog = apps.get_model('portal', 'AuditLog')

    # Blacklist reasons are compact list labels; remove only trailing full stops from
    # existing rows. Other punctuation and the actual reason text remain untouched.
    for row in SourceBlacklist.objects.exclude(reason='').only('pk', 'reason').iterator(chunk_size=500):
        cleaned=(row.reason or '').rstrip().rstrip('.').rstrip()
        if cleaned != (row.reason or ''):
            SourceBlacklist.objects.filter(pk=row.pk).update(reason=cleaned)

    # 0.11.97 changes reserve semantics from free-form suffix phrases to 2-15 letter
    # article-native extensions. Old reserves may contain title-shaped values, so let
    # them regenerate lazily from each article on the next Test & Generate.
    TrackingSuffixReserve.objects.all().update(suffixes=[], cursor=0)

    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.97').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.97',
            summary='ScoutBox upgraded to version 0.11.97.',
            metadata={
                'version': '0.11.97',
                'release': 'native tracking suffixes, compact tracking editor, discovery translation protection and list UI repairs',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0168_v01196_tracking_stats_ui')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
