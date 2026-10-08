# ScoutBox 0.11.94

## Resource Usage: fix the collection path, not the drawing

The apparent six-hour/long-range chart failure had two real data-collection causes. ResourceSample creation was still scheduled through Celery Beat, so a stopped/restarted scheduler or delayed queue could leave multi-hour holes even though the chart itself was working. CPU and RAM could later reappear from container-side fallbacks, while macOS GPU utilization depends on the host telemetry bridge and therefore showed a later start when that bridge had not been publishing.

0.11.94 moves periodic ResourceSample capture to a dedicated `telemetry_sampler` service running a monotonic 15-second loop. It no longer depends on Celery Beat, Redis queue latency, or AI/search workers. On macOS, `start_host_telemetry.sh` now accepts the launchd bridge only after it observes a fresh host snapshot; otherwise it falls back to the portable supervised process path. Existing historical gaps are not fabricated or backfilled.

Chart canvas text remains device-pixel-ratio aware and uses slightly stronger 11px labels/legends for clearer rendering.

## Tracking Links and DOCX checking

- Document-link Test now loads only the path relative to the configured Blog Base URL (for example `ch375`), not the full article URL.
- The informational banner is at the top of the dialog and changes from the scan count to the “URL loaded…” instruction after a Test-row click.
- Blog Base URL label and field share one compact row.
- Removed the redundant “Check links in a DOCX file” heading/divider.
- The DOCX result grid remains Link / Page Title / Test, five rows per page, with a visible footer pager and extra bottom clearance.
- The embedded dialog is allowed to scroll and has a larger measured height ceiling so its pager cannot be clipped.
- Tracking Links Clicks is explicitly sortable and reserves space for its sort glyph.

## List/UI follow-ups

- Applications & Outreach first column is now `ENTRY INFO`.
- Opportunities first column is now `ROLE INFO`.
- AI Requests first column is now `Task Info`.
- Address Book defaults to Created descending (latest first), with the Created header showing the descending state.
- Exhausted Facebook Page-title lookups use a regular-weight yellow exclamation mark and a normal cursor.
- Shared date-range filter buttons receive right-side clearance, including Email History and Resource Usage.
- Removed the obsolete high-level Statistics metric strip; detailed tables, charts, and the activity map remain.
