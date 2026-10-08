from pathlib import Path

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.94'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.94'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.94'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.94'
assert (root/'docs/RELEASE_NOTES_0.11.94.md').exists()
assert '0.11.95, 0.11.96, 0.11.97' in read('RELEASE_POLICY.md')

# Direct resource capture must no longer share Celery Beat / Redis queue timing.
sampler=read('portal/management/commands/sample_resources.py')
compose=read('docker-compose.yml')
settings=read('opportunity_portal/settings.py')
restart=read('restart_scout_box.sh')
assert 'resource_sample_tick.run()' in sampler
assert "parser.add_argument('--interval', type=float, default=15.0)" in sampler
assert 'telemetry_sampler:' in compose
assert '["python", "manage.py", "sample_resources", "--interval", "15"]' in compose
assert 'telemetry_worker:' not in compose
assert '--queues=telemetry' not in compose
assert "'resource-sample-tick'" not in settings
assert "'portal.tasks.resource_sample_tick': {'queue':'telemetry'}" not in settings
assert 'dc build web worker telemetry_sampler discovery_worker forum_worker beat' in restart
assert 'dc up -d worker telemetry_sampler discovery_worker forum_worker beat' in restart

# The macOS host bridge must be accepted only after a fresh snapshot is observed.
host=read('scripts/start_host_telemetry.sh')
assert "captured_at" in host and 'time.time()-stamp < 20' in host
assert 'launchctl bootout "$DOMAIN" "$PLIST"' in host
assert 'nohup "$PYTHON_BIN" "$ROOT/scripts/host_telemetry.py"' in host

# Tracking Link document workflow: short path only, top status, no redundant heading,
# 5 rows per page, visible pager, scrollable embedded frame.
rules=read('templates/portal/link_rules.html')
links=read('templates/portal/links.html')
assert 'trackingShortPath(url)' in rules
assert "el.value=trackingShortPath(url)" in rules
assert 'URL loaded from Document Link Check. Click Test & Generate to resolve and generate it.' in rules
assert 'id="tracking-dialog-status"' in rules
assert 'Check links in a DOCX file' not in rules
assert 'tracking-blog-base-row' in rules
assert '<th>Link</th><th>Page title</th><th data-nosort>Test</th>' in rules
assert 'data-page-size="5"' in rules
assert 'data-pager-nav="tracking-docx-table"' in rules
assert 'Math.min(760,height)' in rules
assert 'scrolling="auto"' in links
assert 'Math.min(760,available,requested)' in links
assert '<th data-sortable class="click-count-col sortable">Clicks</th>' in links

# Requested labels and default Address Book ordering.
assert 'ENTRY INFO' in read('templates/portal/applications.html')
assert 'ROLE INFO' in read('templates/portal/opportunities.html')
assert '>Task Info</a>' in read('templates/portal/gpt_log.html')
views=read('portal/views.py')
assert "contacts=list(qs.order_by('-created_at','-pk')[:1000])" in views
contacts=read('templates/portal/contacts.html')
assert 'data-sort-direction="desc"' in contacts and '>Created</th>' in contacts
assert "data-sort=\"{{c.created_at|date:'YmdHis'}}\"" in contacts

# UI polishing requested in the final 0.11.94 round.
css=read('portal/static/portal/app.css')
assert '.facebook-title-unavailable{font-weight:400!important;cursor:default!important}' in css
assert '.history-range-apply{margin-right:8px!important}' in css
assert '.resource-date-form>.icon-btn:last-of-type{margin-right:8px!important}' in css
assert '.tracking-scan-footer{margin-top:10px!important;margin-bottom:18px!important' in css
assert '#tracking-table th.click-count-col.sortable:after{display:block!important' in css
assert '.embedded-page{overflow-x:hidden!important;overflow-y:auto!important}' in css

facebook=read('templates/portal/facebook_pages.html')
assert 'facebook-title-unavailable' in facebook and '>!</span>' in facebook

# The obsolete Statistics metric strip/live updater is gone; detailed analytics stay.
stats=read('templates/portal/stats.html')
assert 'stats-metric-strip' not in stats
assert 'stats_live' not in stats
assert 'Discovery Source' in stats and 'stats-chart-grid' in stats

# Chart text should use DPR-aware canvases and stronger 11px rendering.
telemetry=read('templates/portal/telemetry.html')
assert 'Math.round(w*dpr)' in telemetry and 'x.setTransform(sx,0,0,sy,0,0)' in telemetry
assert '600 11px ui-sans-serif' in telemetry
assert 'Math.round(w*dpr)' in stats and 'x.setTransform(sx,0,0,sy,0,0)' in stats
assert '600 11px ui-sans-serif' in stats

# Release migration is additive/audit-only: do not invent historical resource samples.
migration=read('portal/migrations/0166_v01194_telemetry_ui_followups.py')
assert "('portal', '0165_v01193_chart_location_ui_repairs')" in migration
assert '0.11.94' in migration
assert 'ResourceSample' not in migration

print('ScoutBox 0.11.94 regression checks passed')
