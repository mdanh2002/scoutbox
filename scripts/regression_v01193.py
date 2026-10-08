from pathlib import Path
root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.93'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.93'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.93'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.93'
assert (root/'docs/RELEASE_NOTES_0.11.93.md').exists()
assert '0.11.94, 0.11.95, 0.11.96' in read('RELEASE_POLICY.md')

rules=read('templates/portal/link_rules.html')
assert '<th>Link</th><th>Page title</th><th data-nosort>Test</th>' in rules
assert 'data-page-size="5"' in rules
assert 'tracking-scan-link-cell' in rules and 'tracking-scan-title-cell' in rules
assert '<td class="tracking-scan-single-line"' not in rules
assert 'data-pager-nav="tracking-docx-table"' in rules

css=read('portal/static/portal/app.css')
assert '#tracking-docx-table th,#tracking-docx-table td{display:table-cell!important' in css
assert '#tracking-table th,#tracking-table td{vertical-align:middle!important}' in css
assert '#gpt-log-table col.gpt-col-task{width:205px!important}' in css
assert '#gpt-log-table col.gpt-col-runtime{width:168px!important}' in css
assert '.email-preview-meta-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important' in css
assert '#apps-table th:nth-child(2),#apps-table td:nth-child(2){width:34%!important' in css
assert '#opportunity-table th:nth-child(2),#opportunity-table td:nth-child(2){width:265px!important' in css
assert '.facebook-title-unavailable' in css

email=read('templates/portal/email_history.html')
assert 'email-preview-meta-grid' in email
assert "[['When',d.when],['Type',d.kind],['Server',d.server],['From',d.sender],['To',d.recipients],['Provider ID',d.message_id]]" in email
assert "+' · '+" not in email[email.index('async function viewMail'):]

apps=read('templates/portal/applications.html')
opps=read('templates/portal/opportunities.html')
assert 'Position / Organization' in apps and '>Updated</th>' in apps
assert 'Position / Organization' in opps

facebook=read('templates/portal/facebook_pages.html')
assert 'facebook-title-unavailable' in facebook and ">!</span>" in facebook
assert "{% icon 'clock' %}" in facebook

tel=read('templates/portal/telemetry.html')
assert 'Math.round(w*dpr)' in tel and 'x.setTransform(sx,0,0,sy,0,0)' in tel
assert "500 10px ui-sans-serif" in tel
stats=read('templates/portal/stats.html')
assert 'Math.round(w*dpr)' in stats and 'x.setTransform(sx,0,0,sy,0,0)' in stats

settings=read('opportunity_portal/settings.py')
compose=read('docker-compose.yml')
assert "'portal.tasks.resource_sample_tick': {'queue':'telemetry'}" in settings
assert 'telemetry_worker:' in compose and '--queues=telemetry' in compose
assert 'telemetry_worker: {condition: service_started}' in compose

views=read('portal/views.py')
assert "status='running',progress=10,message='Testing external statistics data source'" in views
assert "task=blog_stats_test_job.delay(job.pk,cfg.pk)" not in views[views.index('def blog_stats_test_async'):views.index('def _recycle_item_key')]
settings_tpl=read('templates/portal/settings.html')
assert "out.textContent='Testing…'" in settings_tpl and 'if(d.finished)' in settings_tpl

location=read('portal/services/location.py')
mailbox=read('portal/services/mailbox.py')
assert "facts.get('description_html')" in location
assert 'jobicy_snapshot_html' in location
assert "role_items=parse_location_items(role_location" in mailbox
migration=read('portal/migrations/0165_v01193_chart_location_ui_repairs.py')
assert "('portal','0164_v01192_followup_repairs')" in migration
assert "version='0.11.93'" in migration
assert 'Remote\\s+from' in migration

print('ScoutBox 0.11.93 regression checks passed')
