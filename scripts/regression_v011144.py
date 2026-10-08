from pathlib import Path
import importlib.util
import sys
import time

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.144'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.144'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.144'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.144'
assert (root/'docs/RELEASE_NOTES_0.11.144.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-29 08:40:00'" in read('opportunity_portal/settings.py')
assert 'The release following 0.11.144 is 0.11.145' in read('RELEASE_POLICY.md')

models=read('portal/models.py')
assert 'gpu_sample_age_seconds = models.FloatField(null=True, blank=True)' in models
assert "gpu_telemetry_state = models.CharField(max_length=24, default='legacy', blank=True)" in models
assert 'class ResourceHourly(models.Model):' in models
assert "hour = models.DateTimeField(unique=True, db_index=True)" in models
assert 'gpu_stale_count = models.PositiveIntegerField(default=0)' in models

resources=read('portal/services/resources.py')
assert 'GPU_CARRY_FORWARD_SECONDS=15*60' in resources
assert 'def bridge_telemetry_status()' in resources
assert 'def gpu_telemetry_detail_with_status()' in resources
assert 'def capture_resource_sample(*, carry_seconds=GPU_CARRY_FORWARD_SECONDS):' in resources
assert "state='stale_carry'" in resources
assert 'def _merge_hourly_sample(sample):' in resources

# The host bridge itself must retain a last-good reading during the bounded stale window
# and explicitly mark it stale rather than converting it to None after 30 seconds.
spec=importlib.util.spec_from_file_location('scoutbox_host_telemetry',root/'scripts/host_telemetry.py')
ht=importlib.util.module_from_spec(spec); sys.modules[spec.name]=ht; spec.loader.exec_module(ht)
now=time.time()
stale=ht.GpuSampler(interval=5,max_age=900,initial_state={
    'gpu_percent':73.0,'gpu_label':'Apple M5','gpu_sample_at':now-60,
})
state=stale.read()
assert state['gpu_percent']==73.0
assert state['gpu_telemetry_state']=='stale'
expired=ht.GpuSampler(interval=5,max_age=900,initial_state={
    'gpu_percent':73.0,'gpu_label':'Apple M5','gpu_sample_at':now-901,
})
expired_state=expired.read()
assert expired_state['gpu_percent'] is None
assert expired_state['gpu_telemetry_state']=='unavailable'

host=read('scripts/host_telemetry.py')
assert 'max_age=max(900.0,args.gpu_interval*12)' in host
assert "data['gpu_telemetry_state']=gpu_state.get('gpu_telemetry_state')" in host
assert "data['gpu_sample_at']=gpu_state.get('gpu_sample_at')" in host

migration=read('portal/migrations/0216_v011144_telemetry_continuity.py')
assert "dependencies=[('portal','0215_v011143_restart_recovery')]" in migration
assert "name='ResourceHourly'" in migration
assert "version='0.11.144'" in migration
assert "'gpu_telemetry_continuity':True" in migration
assert 'TruncHour' in migration and 'bulk_create' in migration

views=read('portal/views.py')
assert 'ResourceHourly.objects.all()' in views
assert "'_hourly_archive':True" in views
assert 'def _resource_telemetry_health(start=None,end=None):' in views
assert "'telemetry_health':_resource_telemetry_health(start,end)" in views
assert "ResourceHourly.objects.all().delete()" in views

template=read('templates/portal/telemetry.html')
assert 'id="resource-telemetry-health"' in template
assert 'GPU coverage:' in template
assert 'function updateTelemetryHealth(h)' in template

sampler=read('portal/management/commands/sample_resources.py')
assert 'GPU telemetry degraded' in sampler
assert 'GPU telemetry recovered' in sampler

smoke=read('scripts/smoke.sh')
assert 'Resource sample freshness' in smoke
assert 'scripts/check_resource_telemetry.py' in smoke
assert 'GPU telemetry freshness' in smoke
assert (root/'portal/tests/test_v011144.py').exists()

# Earlier fixes remain packaged.
assert (root/'portal/migrations/0215_v011143_restart_recovery.py').exists()
assert (root/'portal/migrations/0214_v011142_facebook_page_title_wrap.py').exists()
assert (root/'portal/migrations/0213_v011141_source_coverage_integrity.py').exists()
assert 'ScoutBox/0.11.144' in read('portal/services/search.py')

print('ScoutBox 0.11.144 targeted regression checks passed')
