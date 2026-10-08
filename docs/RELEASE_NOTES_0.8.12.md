# ScoutBox 0.8.12 release notes

## Read-state reliability

- Opportunities and Market Studies render only unread Role/Company values in bold; read rows use normal weight.
- Bulk Mark as Read / Mark as Unread selection now reads checked row controls directly, independent of form ownership.
- Opening/interacting with an item persists its read state through the dedicated endpoint; browser-back reconciliation keeps the visible state consistent.

## Discovery and opportunity presentation

- Search provider configured-but-unused status uses a new blue `provider_ready_unused` icon and remains distinct from yellow elevated-error/zero-result warnings.
- Opportunities remove the status/open-details columns, use status-tinted Role/Company cells plus a legend, and retain only the blacklist row action.
- Source icons are category-specific. Raw opportunity HTML is reduced to compact paragraphs, bold text and safe links.
- Market Studies uses the same five-bar Fit signal as Opportunities and filters general search engines, job boards and social-media platforms. Existing general-platform Market Studies rows are cleaned by migration.

## Campaigns

- Campaign list includes Next Run for scheduled campaigns; Run History shows the next scheduled run.
- More Criteria is vertically arranged for easier scanning.
- Campaign Templates use row selection, Select All and Delete Selected; per-template Delete is removed, and actions are spaced under an Actions heading.
- Campaign list no longer has a redundant Open/Actions column because the campaign name is the link.

## Data/list refinements

- Blacklist adds Date Added.
- Applied Roles adds Date Added; imported/applied records stamp the value when they enter the applied-role workflow.
- Application Draft Updated timestamps are kept on one line.
- Company display suppresses malformed `Reason: ...` pseudo-company values.

## Dashboard, statistics and resources

- Dashboard activity/system controls are consolidated and the Pause Search action is top-right of the activity card.
- The global page-header clock uses `dd/mm/yyyy HH:mm:ss`; Dashboard Diagnostics refresh sits beside its heading; Recent Campaigns shows the next scheduled campaign.
- Resource Usage aligns Input Tokens and its purpose table; the purpose donut is centered so long labels cannot clip the chart.
- Statistics expands the remaining six summary metrics to fill the available width.

## Performance Lab

- Completed background tests refresh both the run table and detail modals.
- Post Age Analysis exposes its full evidence/result text and raw metadata.
- DOCX→PDF results provide a downloadable generated PDF when conversion succeeds.
