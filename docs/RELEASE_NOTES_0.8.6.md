# ScoutBox 0.8.6 Release Notes

ScoutBox 0.8.6 focuses on restoring configuration access, making list pages visually consistent, and improving opportunity/Market Studies review workflows without reintroducing duplicate navigation.

## System Configuration and navigation

- Restored the complete System Configuration navigation in a single shared bar: General, Search & Processing, Search Sources, Email, Tracking Links, AI & Discovery, ToughDev Stats, Administrators and Maintenance.
- Fixed the settings JavaScript selector so panel switching only hides/shows content panels and never treats navigation links as panels.
- Kept one System Configuration tab bar per configuration page; no second/duplicate tab strip is rendered.
- Renamed Profile, CV & Preferences to Candidate Profile and removed the redundant in-page Candidate Profile heading.
- Renamed Search Scope to Engagement Preferences and compacted its layout.
- Moved Logout to the bottom of the sidebar below the copyright/last-modified block.

## List and toolbar cleanup

- Market Studies: removed the redundant Leads heading; search, read filter, Rows, XLSX export, bulk actions, Manual Scan and Add Lead are aligned in the top toolbar; scan status/progress sits immediately below it.
- Campaigns: compact list toolbar; Created and Last Run columns; select-all/row-select; Delete Selected and confirmed Delete All.
- Opportunities: compact search/status/read/Rows/XLSX toolbar; read/unread state and Applied Date column.
- Applied Roles: removed duplicate heading; Import Applied Roles is next to Delete Selected and uses matching sizing.
- Application Drafts: removed duplicate heading/tab treatment; Add Manually is a toolbar button next to Delete Selected with matching sizing.
- Address Book: removed duplicate heading; Add Contact is beside Search; row/select-all checkboxes; Delete Selected and confirmed Delete All; only Edit remains as the per-row management action.
- Blacklist: no Blocked Sources heading; Add Domain, Reset to Defaults and Delete Selected share the same button sizing/spacing; Reset remains confirmed; domains are clickable in a new tab.
- Audit Log: removed the duplicate in-card heading.
- XLSX export placement remains immediately to the right of Rows/items-per-page wherever those controls are paired.

## Opportunity review

- Opportunity detail suppresses duplicate Search URL / Target URL values and shows a single Source / Target URL row when they resolve to the same URL.
- Post Age is now a compact KPI beside Status, Fit, Added and Channel instead of a large standalone section; detailed evidence remains available in a disclosure panel.
- Job / Lead Text now supports AI summarization through the configured Page Summarization route. ScoutBox stores a source hash with each summary, identifies stale summaries, can refresh them, and keeps the full raw source text behind View raw text.
- Opportunities are marked read when opened. Existing records are migrated as read so only newly arriving items appear as New after upgrade.
- Applied Date records the first Create Application Draft / Prepare Application request and is backfilled from existing Application records where available.

## Market Studies

- Market Studies records have New/Read state and are marked read when details are opened.
- Areas display strips legacy prefixes such as Relevant work:, Relevant technical work:, Technical areas: and similar labels. The migration also cleans stored legacy values.
- Prepare Application and Details actions are consistently aligned and spaced.
- Lead detail suppresses the Search URL row when Search URL and Target URL are the same.
- Select All, row selection, Delete Selected and confirmed Delete All are available.

## Resource and discovery diagnostics

- Resource Usage has a cleaned-up Today / Week / Month / All + From / To filter bar.
- Search Provider Performance remains available with requests, returned pages, unique/applied matches, duplicates, errors, latency, downloaded bytes and last error.
- Statistics includes opportunity counts attributed to discovery sources (not search providers), with visual/table representation.
- Discovery Sources links ordinary external source presets to their home pages in a new tab and retains the expanded excluded/low-value marketplace group.

## Data migration

Migration `portal/0008_v086_ui_read_summary.py` adds Opportunity/Market Studies read state, Opportunity application-draft-requested timestamp, the AI summarize background-job kind, backfills existing application dates, marks pre-upgrade records read, and normalizes legacy Market Studies Areas labels.
