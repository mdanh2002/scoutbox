# ScoutBox 0.9.36

## Recovered JSON detail rendering

AI Requests now treats a validated **Recovered response** as authoritative structured output in the detail popup. The detail endpoint normalizes the corrected payload and also returns its parsed JSON value; the browser renders that value rather than reclassifying it through the malformed-text fallback. If an older recovered row contains the original truncated text in `output_text`, the detail endpoint can rebuild the corrected display from the preserved `raw_output_text` without inventing any data.

The recovery notice uses a dedicated informational treatment, and the recovered-response status glyph is now a simple circle-check icon. The malformed-response icon remains separate for payloads ScoutBox could not repair safely.

## Dashboard activity timing

ScoutBox activity rows now combine campaign timing into one compact inline phrase. A same-day campaign is shown in the form `started 29 Aug 10:05 · last activity 10:47`; cross-day activity includes the second date, while the current year is omitted. This removes the previous stacked `started on ...` / `last activity ...` presentation and avoids repeating the year.

## Upgrade

No database migration is required for 0.9.36. Keep the existing `.env` and Docker volumes, replace the application files, then run `./restart_scout_box.sh`.
