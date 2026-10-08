from pathlib import Path

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.95'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.95'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.95'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.95'
assert (root/'docs/RELEASE_NOTES_0.11.95.md').exists()

m166=read('portal/migrations/0166_v01194_telemetry_ui_followups.py')
assert "action='version_upgraded'" in m166
assert "version='0.11.94'" in m166
assert "summary='ScoutBox upgraded to version 0.11.94.'" in m166
assert "metadata={" in m166
assert 'detail__contains' not in m166
assert 'detail=' not in m166
assert 'ResourceSample' not in m166

m167=read('portal/migrations/0167_v01195_migration_hotfix.py')
assert "('portal', '0166_v01194_telemetry_ui_followups')" in m167
assert "action='version_upgraded'" in m167
assert "version='0.11.95'" in m167
assert "summary='ScoutBox upgraded to version 0.11.95.'" in m167
assert 'detail' not in m167

# Validate the fields used by both release audit migrations against the actual
# AuditLog model declaration so this exact regression cannot recur silently.
model=read('portal/models.py')
section=model[model.index('class AuditLog'):model.index('class PerformanceRun')]
for field in ('version','actor','action','summary','metadata'):
    assert f'{field} =' in section
assert 'detail =' not in section

print('ScoutBox 0.11.95 migration hotfix regression checks passed')
