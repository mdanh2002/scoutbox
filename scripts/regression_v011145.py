from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.145'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.145'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.145'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.145'
assert (root/'docs/RELEASE_NOTES_0.11.145.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-29 10:17:00'" in read('opportunity_portal/settings.py')
assert 'The release following 0.11.145 is 0.11.146' in read('RELEASE_POLICY.md')

template=read('templates/portal/telemetry.html')
assert 'id="resource-telemetry-health"' not in template
assert '<b>Hardware archive:</b>' not in template
assert '<b>Hardware coverage:</b>' not in template
assert '<b>GPU coverage:</b>' not in template
assert '<b>GPU state:</b>' not in template
assert 'function updateTelemetryHealth(h)' not in template
assert 'updateTelemetryHealth(d.telemetry_health)' not in template

css=read('portal/static/portal/app.css')
assert '.resource-telemetry-health' not in css
assert '.resource-telemetry-warning' not in css

# The 0.11.144 telemetry integrity backend remains packaged and active.
models=read('portal/models.py')
assert 'class ResourceHourly(models.Model):' in models
assert 'gpu_sample_age_seconds = models.FloatField(null=True, blank=True)' in models
resources=read('portal/services/resources.py')
assert 'GPU_CARRY_FORWARD_SECONDS=15*60' in resources
assert 'def capture_resource_sample(*, carry_seconds=GPU_CARRY_FORWARD_SECONDS):' in resources
views=read('portal/views.py')
assert 'def _resource_telemetry_health(start=None,end=None):' in views
assert "'telemetry_health':_resource_telemetry_health(start,end)" in views
assert 'ResourceHourly.objects.all()' in views
assert 'scripts/check_resource_telemetry.py' in read('scripts/smoke.sh')

migration=read('portal/migrations/0217_v011145_resource_usage_panel_cleanup.py')
assert "dependencies=[('portal','0216_v011144_telemetry_continuity')]" in migration
assert "version='0.11.145'" in migration
assert "'resource_usage_telemetry_panel_removed':True" in migration
assert "'telemetry_continuity_backend_retained':True" in migration

# Earlier release migrations and fixes remain packaged.
assert (root/'portal/migrations/0216_v011144_telemetry_continuity.py').exists()
assert (root/'portal/migrations/0215_v011143_restart_recovery.py').exists()
assert (root/'portal/migrations/0214_v011142_facebook_page_title_wrap.py').exists()
assert (root/'portal/migrations/0213_v011141_source_coverage_integrity.py').exists()
assert 'ScoutBox/0.11.145' in read('portal/services/search.py')

print('ScoutBox 0.11.145 targeted regression checks passed')
