from django.db import migrations, models
from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncHour


def backfill_hourly_and_audit(apps, schema_editor):
    ResourceSample=apps.get_model('portal','ResourceSample')
    ResourceHourly=apps.get_model('portal','ResourceHourly')
    AuditLog=apps.get_model('portal','AuditLog')

    # Preserve whatever detailed hardware history is still present at upgrade time in
    # the compact archive. This is intentionally an aggregate query: even a 90-day raw
    # table produces only ~2,160 hourly rows and does not load every 15-second sample.
    rows=(ResourceSample.objects.annotate(_hour=TruncHour('at')).values('_hour').annotate(
        sample_count=Count('id'),
        cpu_avg=Avg('cpu_percent'),cpu_min=Min('cpu_percent'),cpu_max=Max('cpu_percent'),
        memory_avg=Avg('memory_percent'),memory_min=Min('memory_percent'),memory_max=Max('memory_percent'),
        memory_used_mb=Avg('memory_used_mb'),memory_total_mb=Avg('memory_total_mb'),
        disk_used_mb=Avg('disk_used_mb'),disk_total_mb=Avg('disk_total_mb'),
        gpu_avg=Avg('gpu_percent'),gpu_min=Min('gpu_percent'),gpu_max=Max('gpu_percent'),
        gpu_sample_count=Count('gpu_percent'),
        gpu_label=Max('gpu_label'),
        gpu_vram_used_mb=Avg('gpu_vram_used_mb'),gpu_vram_total_mb=Avg('gpu_vram_total_mb'),
        last_sample_at=Max('at'),
    ).order_by('_hour'))
    batch=[]
    for row in rows.iterator(chunk_size=500):
        hour=row.get('_hour')
        if hour is None:
            continue
        batch.append(ResourceHourly(
            hour=hour,last_sample_at=row.get('last_sample_at'),sample_count=int(row.get('sample_count') or 0),
            cpu_avg=row.get('cpu_avg'),cpu_min=row.get('cpu_min'),cpu_max=row.get('cpu_max'),
            memory_avg=row.get('memory_avg'),memory_min=row.get('memory_min'),memory_max=row.get('memory_max'),
            memory_used_mb=max(0,int(row.get('memory_used_mb') or 0)),memory_total_mb=max(0,int(row.get('memory_total_mb') or 0)),
            disk_used_mb=max(0,int(row.get('disk_used_mb') or 0)),disk_total_mb=max(0,int(row.get('disk_total_mb') or 0)),
            gpu_avg=row.get('gpu_avg'),gpu_min=row.get('gpu_min'),gpu_max=row.get('gpu_max'),
            gpu_sample_count=int(row.get('gpu_sample_count') or 0),gpu_stale_count=0,
            gpu_label=str(row.get('gpu_label') or '')[:200],
            gpu_vram_used_mb=None if row.get('gpu_vram_used_mb') is None else max(0,int(row.get('gpu_vram_used_mb') or 0)),
            gpu_vram_total_mb=None if row.get('gpu_vram_total_mb') is None else max(0,int(row.get('gpu_vram_total_mb') or 0)),
        ))
        if len(batch)>=500:
            ResourceHourly.objects.bulk_create(batch,ignore_conflicts=True); batch=[]
    if batch:
        ResourceHourly.objects.bulk_create(batch,ignore_conflicts=True)

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.144').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.144',summary='ScoutBox upgraded to version 0.11.144.',
            metadata={
                'release':'0.11.144',
                'gpu_telemetry_continuity':True,
                'resource_hourly_archive':True,
                'telemetry_freshness_watchdog':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0215_v011143_restart_recovery')]
    operations=[
        migrations.AddField(
            model_name='resourcesample',name='gpu_sample_age_seconds',
            field=models.FloatField(blank=True,null=True),
        ),
        migrations.AddField(
            model_name='resourcesample',name='gpu_telemetry_state',
            field=models.CharField(blank=True,default='legacy',max_length=24),
        ),
        migrations.AddField(
            model_name='resourcesample',name='host_telemetry_age_seconds',
            field=models.FloatField(blank=True,null=True),
        ),
        migrations.CreateModel(
            name='ResourceHourly',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('hour',models.DateTimeField(db_index=True,unique=True)),
                ('last_sample_at',models.DateTimeField(blank=True,null=True)),
                ('sample_count',models.PositiveIntegerField(default=0)),
                ('cpu_avg',models.FloatField(blank=True,null=True)),('cpu_min',models.FloatField(blank=True,null=True)),('cpu_max',models.FloatField(blank=True,null=True)),
                ('memory_avg',models.FloatField(blank=True,null=True)),('memory_min',models.FloatField(blank=True,null=True)),('memory_max',models.FloatField(blank=True,null=True)),
                ('memory_used_mb',models.PositiveIntegerField(default=0)),('memory_total_mb',models.PositiveIntegerField(default=0)),
                ('disk_used_mb',models.PositiveIntegerField(default=0)),('disk_total_mb',models.PositiveIntegerField(default=0)),
                ('gpu_avg',models.FloatField(blank=True,null=True)),('gpu_min',models.FloatField(blank=True,null=True)),('gpu_max',models.FloatField(blank=True,null=True)),
                ('gpu_sample_count',models.PositiveIntegerField(default=0)),('gpu_stale_count',models.PositiveIntegerField(default=0)),
                ('gpu_label',models.CharField(blank=True,max_length=200)),
                ('gpu_vram_used_mb',models.PositiveIntegerField(blank=True,null=True)),('gpu_vram_total_mb',models.PositiveIntegerField(blank=True,null=True)),
                ('updated_at',models.DateTimeField(auto_now=True)),
            ],
            options={'ordering':['-hour']},
        ),
        migrations.RunPython(backfill_hourly_and_audit,migrations.RunPython.noop),
    ]
