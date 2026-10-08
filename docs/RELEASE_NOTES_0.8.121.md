# ScoutBox 0.8.121

This maintenance release keeps the 0.8.120 discovery pipeline intact while improving diagnostics and several list/dashboard details.

- Resource Usage now aggregates matching Usage Events by type, provider/model and stage so pre-AI rejection/filter activity is easier to reconcile with raw search-provider Returned Pages. Raw telemetry is unchanged.
- AI Requests treats an empty provider response as an empty Output cell. The list no longer rewrites completed requests to failed merely because output is blank, and error text is not substituted into Output. Migration `0070_v08121_ai_empty_output_repair.py` repairs historical rows created by the former synthetic `AI provider returned no visible output.` behavior.
- Search Activity, AI Requests, Audit Trail, Email History and Recycle Bin support All, 24h, 3d, 7d, 30d and Custom ranges. Exports honor the active range.
- Dashboard activity x-axis labels are spaced/rotated for readability.
- Opportunity and Hidden Lead Fit icons are vertically centered within Summary cells.
- Recycle Bin Item Title and Item Info columns have equal widths.
- ScoutBox-owned disk-usage values display to one decimal place.

The low number of Local AI requests relative to raw Returned Pages is not changed in this release: Local Discovery still deduplicates and applies URL, fetch, language, aggregate-page and profile-relevance gates before the local AI review. Aggregated Resource Usage events make those stages easier to inspect.
