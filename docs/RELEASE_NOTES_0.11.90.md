# ScoutBox 0.11.90

## Discovery and blacklist

- Removed generic workflow boilerplate from blacklist reasons, cleaned existing stored reasons during upgrade, and sanitized all future writes and exports while preserving audit records.
- Kept Naver eligible for international discovery and retained market-specific provider routing so DuckDuckGo does not default unrelated market passes to `wt-wt`.
- Compacted Discovery Activity and Discovery Source Activity result metrics; Results is left-aligned and unsortable, with latency and size immediately after it.
- Compacted Usage Events token and AI-search metrics into one Usage cell, with Pages and Avg Latency immediately after Requests.

## Facebook Pages and Tracking Links

- Added clear New/Seen filter state, distinct unread-row styling, neutral delete styling, safer toolbar hit areas, newest-first default sorting and hover-only Page ID underlining.
- Bounded Facebook Page title validation: unresolved titles become an explicit unavailable/retry state instead of remaining pending forever.
- Kept Tracking Links inside its card, balanced Article and Application widths, refreshed article titles from live HTML, and disabled Application links when their records no longer exist.
- Contained the Add Tracking Link dialog, removed its unnecessary empty height and outer scrolling, and limited DOCX scan results to five single-line rows per page with navigation.

## Resource Usage and histories

- Fixed rolling CPU/RAM/Token chart bounds so 3-, 7-, 14- and 30-day views span the selected period instead of collapsing to today's retained samples.
- Made Downloaded open the restored data-breakdown dialog and standardized every Resource Usage metric hover to a border highlight without a background change.
- Reduced Token Usage and Discovery Performance panels to content height and standardized their ring summaries and legend alignment.
- Moved date/time to the last column in Search Activity, AI Requests, Audit Trail and every Email History tab, including exports.
- Moved Recycle Bin Item Date and Date Deleted to the final columns, ordered Item Date then Date Deleted, widened Item Type, and matched the export order.
- Added a searchable, record-derived multiselect Audit Trail version filter with an Unknown option and aligned its footer controls.
- Moved Email History item counts to the top right, aligned the date range there, removed the duplicate footer count and removed the redundant mail-history hint.

## Presentation consistency

- Refined map popovers so only the smaller job title is linked and underlined on hover.
- Removed redundant upload separators, flattened preferred-minimum rows and aligned Engagement types typography.
- Matched the Dashboard Jobs/Leads/Contacts balance line typography to the Apple M5/local-model status line.

