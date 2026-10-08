#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.47 Applications & Outreach controls."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION').read_text().strip()
release = (ROOT / 'RELEASE_ID').read_text().strip()
assert version == '0.11.47', 'VERSION is not 0.11.47'
assert release == 'ScoutBox 0.11.47', 'RELEASE_ID stale'
view = (ROOT / 'portal/views.py').read_text(encoding='utf-8')
tpl = (ROOT / 'templates/portal/applications.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
assert 'status_state=_request_multi_filter_state(request,\'status\',canonicalizer=_canonical_application_status)' in view, 'Application status multi-select state missing'
assert 'channel_state=_request_multi_filter_state(request,\'channel\',canonicalizer=_canonical_application_channel)' in view, 'Application channel multi-select state missing'
assert 'def _apply_application_status_filters' in view and 'status__in=list(wanted)' in view, 'multi-status queryset filter missing'
assert 'def _apply_application_channel_filters' in view and 'opportunity__channel__in=wanted' in view, 'multi-channel queryset filter missing'
assert "history_status_token='__history__'" in view and "stage=='history'" in view, 'legacy History status compatibility missing'
assert 'status_options=status_options' in view and 'channel_options=channel_options' in view, 'template options not passed'
assert 'class="multi-select-filter app-status-filter no-option-icons"' in tpl, 'Status searchable dropdown missing'
assert 'placeholder="Search statuses…"' in tpl, 'Status search field missing'
assert 'name="status_mode"' in tpl and 'name="status" value="{{option.value}}"' in tpl, 'Status mode/checks missing'
assert 'class="multi-select-filter app-channel-filter no-option-icons"' in tpl, 'Channel searchable dropdown missing'
assert 'placeholder="Search channels…"' in tpl, 'Channel search field missing'
assert 'name="channel_mode"' in tpl and 'name="channel" value="{{option.value}}"' in tpl, 'Channel mode/checks missing'
assert tpl.count('onclick="applyMultiSelectFilter(this)">Apply</button>') >= 3, 'Apply-first multi-select buttons missing'
assert 'toolbar-actions-right toolbar-action-cluster' in tpl, 'Applications action cluster should use icon-button styling'
assert 'read-state-filter-button' in tpl and "navigateListFacet('read',this.value)" in tpl, 'Read icon dropdown missing'
assert 'mark-state-action-button' in tpl and 'applicationBulkAction(this.value)' in tpl, 'Mark-as icon dropdown missing'
assert 'title="Read status"' not in tpl, 'old visible Read select should be removed'
assert 'onchange="applicationFilterNavigate(this.value)" title="Application status"' not in tpl, 'old Status native select should be removed'
assert 'onchange="applicationFilterNavigate(this.value)" title="Application channel"' not in tpl, 'old Channel native select should be removed'
assert '.applications-toolbar details.multi-select-filter' in css, 'Applications multi-select shared styling missing'
print('ScoutBox 0.11.47 regression checks passed')
