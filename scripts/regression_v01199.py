from pathlib import Path
import ast

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.99'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.99'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.99'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.99'
assert (root/'docs/RELEASE_NOTES_0.11.99.md').exists()
assert '0.11.100, 0.11.101, 0.11.102' in read('RELEASE_POLICY.md')

# Dashboard gets Campaigns first and Tracking Links immediately before Errors.
dash=read('templates/portal/dashboard.html')
metric=dash[dash.index('<div class="metric-strip span-12 dashboard-metrics-grid">'):dash.index('<div class="card span-12"',dash.index('<div class="metric-strip span-12 dashboard-metrics-grid">'))]
labels=['Campaigns','New opportunities','New Hidden Leads','New Contacts','Facebook Pages','Applications &amp; Outreaches','Replies today','Tracking Links','Errors · 24h']
positions=[metric.index('>'+label+'<') for label in labels]
assert positions==sorted(positions), positions
for key in ('campaigns','tracking_links'):
    assert f"stats.{key}" in metric
    assert f"'{key}'" in dash
views=read('portal/views.py')
assert "'campaigns':Campaign.objects.filter(deleted_at__isnull=True).count()" in views
assert "'tracking_links':TrackingLink.objects.filter(deleted_at__isnull=True).count()" in views

# Tracking editor: no 760px wrap regression; progress belongs on the action button.
links=read('templates/portal/link_rules.html')
css=read('portal/static/portal/app.css')
assert "trackingTestButton('Testing…'" in links
assert "trackingStatus('Resolving the page and preparing the suffix reserve…')" not in links
assert "trackingStatus('Scanning DOCX links…')" not in links
assert '@media(min-width:561px)' in css
assert '.tracking-editor-line,.tracking-docx-inline{display:flex!important;align-items:center!important;flex-wrap:nowrap!important' in css

# Statistics: verbose Acquisition Path helper removed; Token Categories aligns with the two
# provider-combined visualizations.
stats=read('templates/portal/stats.html')
assert 'Fresh direct APIs/feeds and communities are measured separately' not in stats
assert '.telemetry-page #token-categories .token-purpose-grid' in css
assert 'grid-template-columns:minmax(330px,.9fr) minmax(460px,1.4fr)!important' in css

# AI list-only JSON preview puts an ellipsis before the synthetic closing quote.
assert "preview=preview.rstrip()+(' ...' if not preview.rstrip().endswith('...') else '')+'\"'" in views
assert 'row.output_inline_ellipsis' in views
gpt=read('templates/portal/gpt_log.html')
assert 'x.output_truncated and not x.output_inline_ellipsis' in gpt

# Audit summary/data are merged into one wide event cell.
audit=read('templates/portal/audit.html')
assert '<th>Event</th>' in audit
assert '<th>Data</th>' not in audit and '<th>Summary</th>' not in audit
assert 'audit-event-summary' in audit and 'audit-event-data' in audit
assert '#audit-table col.audit-event-col{width:auto!important}' in css

# Email history uses one wrapper/table geometry and stable viewport gutter.
mail=read('templates/portal/email_history.html')
assert mail.count('email-history-table-wrap')==3
assert 'html{scrollbar-gutter:stable}' in css
for table in ('incoming-mail','outgoing-mail','draft-mail'):
    assert f'#{table}' in css

# Search Activity provider icons stay vector and are no longer rendered at a tiny 12px size.
assert '.search-log-provider-cell .provider-kind-icon .svg-icon{width:16px!important;height:16px!important' in css
extras=read('portal/templatetags/portal_extras.py')
assert "'source_search':'<svg" in extras

# Blacklist terminology is now Remark, while the database field remains backward compatible.
blacklist=read('templates/portal/blacklist.html')
assert '>Remark</a></th>' in blacklist
assert blacklist.count('<label>Remark</label><input name="reason"')==2

# Migration uses valid AuditLog fields only.
m171=read('portal/migrations/0171_v01199_ui_consistency.py')
assert "('portal', '0170_v01198_focus_search_ui')" in m171
assert "action='version_upgraded', version='0.11.99'" in m171
assert 'detail' not in m171

print('ScoutBox 0.11.99 targeted regression checks passed')
