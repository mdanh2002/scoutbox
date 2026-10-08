# ScoutBox 0.8.8 release notes

ScoutBox 0.8.8 builds on the verified 0.8.7 package and focuses on non-blocking diagnostics, provider observability, Market Studies reliability, opportunity review, freshness evidence and consistent list/chart presentation. It does not add a database schema migration beyond `portal/0008_v086_ui_read_summary.py`.

## Market Studies, Campaigns and bulk actions

- Fixed the Market Studies rendering path and retained display-time cleanup for legacy `Relevant work:` / `Relevant technical work:` prefixes.
- Market Studies and Opportunities now use email-style unread emphasis: unread rows are bold, the Seen column is hidden, and selected rows can be marked unread from the toolbar.
- Campaign creation opens in a popup and the obsolete New/Rerun tab is removed.
- Campaigns and Market Studies use row selection, Select All and Delete Selected; redundant Delete All controls are not shown on list views that already provide selection-based deletion.
- Blacklist uses Add Item, keeps edit state for the Blocked checkbox, supports URL/path patterns, and provides count/page navigation at the bottom.

## Opportunity detail and post-age diagnostics

- Post Age information opens as a popup rather than expanding inline, and Refresh queues background analysis instead of reloading the page.
- Freshness analysis asks the configured AI freshness stage to interpret publication/update/deadline timestamps in visible article text. Structured metadata remains primary and deterministic date-pattern matching is a fallback.
- Archive.org first/latest captures are compared when available and surfaced as evidence without treating archive capture time as definitive vacancy publication time.
- Extracted Facts includes a raw-JSON debug popup so sparse or malformed enrichment output can be inspected directly.
- Opportunity AI summaries continue to be generated in the background when newly discovered rather than being triggered merely by opening the detail page.

## Search-provider and runtime diagnostics

- Search Sources distinguish healthy, elevated-error, unconfigured/disabled, and successful-request-but-no-result provider states.
- Dashboard provider summary and Recent Errors relay elevated errors and persistent zero-result providers for attention.
- First Run Readiness reports AI runtime facts as information: installed local models, configured cloud providers and GPU/CPU availability, rather than presenting model selection as a generic warning.
- Search Provider Performance is sorted alphabetically by provider.

## Charts, usage and timestamps

- Resource Usage CPU/Memory/GPU chart always records a current sample when needed, renders a percentage Y axis and exposes raw point values on hover.
- Dashboard Discovery Activity charts include numeric Y axes and hoverable raw bar values.
- Statistics opportunity-status/provider charts include Y axes and raw-value hover; Discovery Source Share is a hoverable donut and its table remains full width.
- User-facing activity/history timestamps use day/month/year with seconds where applicable.

## IMAP, tracking and ToughDev integration

- IMAP Browser retains configured Inbox, Drafts and Sent folders even when an IMAP LIST response is incomplete, with clearer spacing between browser controls.
- Tracking Link Test & Generate remains asynchronous and DOCX link rows can push a discovered URL into the tracking-link tester.
- ToughDev URL normalization accepts http/https and www/non-www equivalents while rejecting off-host redirects; read-only SELECT testing remains asynchronous so bad credentials do not block the page.

## Configuration and navigation

- Configuration uses one non-duplicated navigation bar containing General, Search Sources, Email, Tracking Links, AI & Discovery, ToughDev Stats, Users and Maintenance.
- The obsolete Search & Processing destination is hidden; the settings it duplicated remain represented by their owning configuration pages.
- Country autocomplete shows flags, Candidate Profile/Engagement Preferences spacing is tightened, and Maintenance retains its destructive-action caution.
