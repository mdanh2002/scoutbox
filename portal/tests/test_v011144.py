from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from portal.models import PortalSettings, ResourceHourly, ResourceSample
from portal.services.resources import capture_resource_sample
from portal.tasks import retention_cleanup_tick
from portal.views import _resource_sample_rows


TOTALS={
    'memory_used_mb':16000,'memory_total_mb':32000,'memory_percent':50.0,
    'disk_used_mb':100000,'disk_total_mb':500000,'disk_free_mb':400000,
    'cpu_percent':25.0,'cpu_count':10,'hostname':'test','platform':'Darwin arm64',
    'os_label':'macOS','storage_label':'SSD',
}


class ResourceTelemetryContinuityTests(TestCase):
    @patch('portal.services.resources.host_resource_totals', return_value=TOTALS)
    @patch('portal.services.resources.host_cpu_percent', return_value=22.0)
    @patch('portal.services.resources.gpu_telemetry_detail_with_status')
    def test_capture_persists_quality_and_hourly_archive(self, gpu_detail, _cpu, _totals):
        gpu_detail.return_value=(81.0,None,'Apple M5',None,None,{
            'gpu_telemetry_state':'fresh','gpu_sample_age_seconds':2.0,'bridge_age_seconds':1.0,
        })
        sample=capture_resource_sample()
        self.assertEqual(sample.gpu_percent,81.0)
        self.assertEqual(sample.gpu_telemetry_state,'fresh')
        self.assertEqual(sample.gpu_sample_age_seconds,2.0)
        hourly=ResourceHourly.objects.get()
        self.assertEqual(hourly.sample_count,1)
        self.assertEqual(hourly.gpu_sample_count,1)
        self.assertEqual(hourly.gpu_avg,81.0)
        self.assertEqual(hourly.gpu_label,'Apple M5')

    @patch('portal.services.resources.host_resource_totals', return_value=TOTALS)
    @patch('portal.services.resources.host_cpu_percent', return_value=30.0)
    @patch('portal.services.resources.gpu_telemetry_detail_with_status')
    def test_short_gpu_probe_failure_carries_last_measurement_as_stale(self, gpu_detail, _cpu, _totals):
        previous=ResourceSample.objects.create(
            at=timezone.now()-timedelta(seconds=40),cpu_percent=10,memory_percent=45,
            memory_used_mb=14000,memory_total_mb=32000,disk_used_mb=90000,disk_total_mb=500000,
            gpu_percent=72.0,gpu_label='Apple M5',gpu_sample_age_seconds=3.0,gpu_telemetry_state='fresh',
        )
        gpu_detail.return_value=(None,None,'Apple M5',None,None,{
            'gpu_telemetry_state':'bridge_stale','gpu_sample_age_seconds':None,'bridge_age_seconds':50.0,
        })
        sample=capture_resource_sample(carry_seconds=900)
        self.assertEqual(sample.gpu_percent,previous.gpu_percent)
        self.assertEqual(sample.gpu_telemetry_state,'stale_carry')
        self.assertGreaterEqual(sample.gpu_sample_age_seconds,40.0)
        hourly=ResourceHourly.objects.get()
        self.assertEqual(hourly.gpu_sample_count,1)
        self.assertEqual(hourly.gpu_stale_count,1)

    def test_long_range_chart_uses_hourly_archive_when_raw_hour_is_missing(self):
        now=timezone.now().replace(minute=0,second=0,microsecond=0)
        old_hour=now-timedelta(days=5)
        ResourceHourly.objects.create(
            hour=old_hour,last_sample_at=old_hour+timedelta(minutes=59),sample_count=200,
            cpu_avg=25,cpu_min=5,cpu_max=90,memory_avg=55,memory_min=50,memory_max=60,
            memory_used_mb=17000,memory_total_mb=32000,disk_used_mb=100000,disk_total_mb=500000,
            gpu_avg=67,gpu_min=10,gpu_max=99,gpu_sample_count=190,gpu_label='Apple M5',
        )
        ResourceSample.objects.create(
            at=now-timedelta(minutes=10),cpu_percent=20,memory_percent=52,memory_used_mb=16000,
            memory_total_mb=32000,disk_used_mb=100000,disk_total_mb=500000,gpu_percent=80,gpu_label='Apple M5',
        )
        rows=_resource_sample_rows(ResourceSample.objects.all(),now-timedelta(days=7),now,max_points=240)
        self.assertTrue(any(row.get('_hourly_archive') and row.get('gpu_percent')==67 for row in rows))

    def test_daily_retention_does_not_delete_hourly_archive(self):
        settings=PortalSettings.objects.get_or_create(pk=1)[0]
        settings.detailed_log_retention_days=14
        settings.save(update_fields=['detailed_log_retention_days'])
        old=timezone.now()-timedelta(days=40)
        ResourceHourly.objects.create(hour=old,sample_count=1,cpu_avg=1,memory_avg=2,gpu_avg=3,gpu_sample_count=1)
        retention_cleanup_tick.run()
        self.assertTrue(ResourceHourly.objects.filter(hour=old).exists())
