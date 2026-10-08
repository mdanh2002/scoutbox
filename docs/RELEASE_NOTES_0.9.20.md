# ScoutBox 0.9.20

## About page hierarchy

- **Terminal & SQL examples** now uses the same prominent heading size/color as **Database Info**, with a terminal icon on the left.
- **Useful scripts & key files** uses the same heading tier with a folder/check icon.
- Existing learning/reference content and command layouts remain unchanged.

## Raw Resource Usage export

- The CPU/RAM/Tokens XLSX export no longer reuses the chart's sampled/bucketed dataset.
- It exports every stored `ResourceSample` in the selected period, ordered by timestamp.
- Month/All charts may still bucket or downsample in the browser path for performance; that does not affect XLSX rows.
- The workbook also includes disk used/total and GPU model fields in addition to the existing CPU, RAM, GPU, VRAM, request and token columns.

## Remote indicator cleanup

- Hybrid captions are normalized to the concise **Hybrid** label even if older AI metadata contains a longer custom label.
- The on-site cross is rendered as a centered SVG so its vertical alignment matches the other remote-status icons.

No database migration is introduced in 0.9.20.
