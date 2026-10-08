# ScoutBox 0.11.93

ScoutBox 0.11.93 repairs Resource Usage sampling continuity, chart canvas sharpness, DOCX link scanning layout, Address Book source-region fidelity, and several dense list layouts.

## Changes

- Rebuilt Document Link Check as a strict three-column Link / Page Title / Test grid with five rows per client page and footer navigation.
- Isolated the 15-second ResourceSample task on a dedicated `telemetry` Celery worker so long AI/search jobs cannot starve CPU/RAM/GPU collection and create multi-hour chart gaps.
- Corrected canvas backing-store scaling for Resource Usage, Token Usage, Discovery Performance and Market Coverage so legends/axis text remain crisp at fractional display scale/browser zoom.
- Reduced AI Requests Task / Related and Runtime / Model widths to return space to Input and Output previews.
- Reformatted Email History preview metadata as labelled two-column rows while retaining the light HTML message canvas.
- Vertically aligned Tracking Links rows.
- Preserved Jobicy's visible `Remote from` region (for example EMEA) ahead of expanded structured country arrays, repaired matching stored Opportunities/Address Book contacts during upgrade, and made future Address Book promotion prefer the concise role region.
- Renamed Applications / Outreach and Opportunities `Role / Company` to `Position / Organization`; compacted Contact / URL, Status and Updated columns; widened the primary opportunity/entity column and reduced Summary space.
- Facebook Page title exhaustion after four automatic attempts now displays a yellow exclamation mark rather than the pending clock.
- External Statistics `Test connection` now performs its short read-only check immediately instead of waiting behind the background-worker queue.

## Upgrade

Migration `0165_v01193_chart_location_ui_repairs` repairs Jobicy source-region rows where a visible recruiter region was previously expanded into many countries and records the 0.11.93 upgrade audit event.
