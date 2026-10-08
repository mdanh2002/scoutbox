from pathlib import Path

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.100'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.100'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.100'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.100'
assert (root/'docs/RELEASE_NOTES_0.11.100.md').exists()
assert '0.11.101, 0.11.102, 0.11.103' in read('RELEASE_POLICY.md')

# Dashboard hotfix: Tracking Links metric must reverse the actual route name.
dash=read('templates/portal/dashboard.html')
assert "href=\"{% url 'links' %}\"" in dash
assert "{% url 'tracking_links' %}" not in dash
urls=read('portal/urls.py')
assert "views.links_view,name='links'" in urls

# Tracking editor rows share one fixed label gutter, including the DOCX row.
links=read('templates/portal/link_rules.html')
css=read('portal/static/portal/app.css')
assert 'tracking-editor-label-spacer' in links
assert '.tracking-editor-line>label,' in css
assert '.tracking-editor-label-spacer{' in css
assert 'flex:0 0 116px!important' in css
assert '.tracking-docx-inline .tracking-docx-file{min-width:0!important;flex:1 1 500px!important}' in css

# Acquisition Path has no empty helper/toolbar row: export lives in the card heading.
stats=read('templates/portal/stats.html')
assert 'stats-acquisition-toolbar' not in stats
assert '<h3 class="stats-card-heading"><span>Acquisition Path</span><a class="icon-btn export-btn"' in stats
assert 'Fresh direct APIs/feeds and communities are measured separately' not in stats

# Audit Trail must not repeat object_title when it is identical to summary.
audit=read('templates/portal/audit.html')
assert 'x.metadata.object_title != x.summary' in audit
assert '({{x.object_type}}{% if x.object_id %} {{x.object_id}}{% endif %})' in audit

# Migration uses the valid AuditLog schema and links to 0.11.99.
m172=read('portal/migrations/0172_v011100_dashboard_hotfix.py')
assert "('portal', '0171_v01199_ui_consistency')" in m172
assert "action='version_upgraded', version='0.11.100'" in m172
assert 'detail' not in m172

print('ScoutBox 0.11.100 targeted regression checks passed')
