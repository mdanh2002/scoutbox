# ScoutBox 0.8.43 release notes

ScoutBox 0.8.43 is a focused UI, diagnostics, routing and observability refinement of 0.8.42. Unrelated discovery/application behavior is unchanged.

## Campaigns and discovery charts

- The Campaign navigation badge now shows only the number of enabled/running campaigns, e.g. `4`; it is hidden at zero and explains itself on hover.
- Searchable Campaign filters show a left-side checkmark on the selected campaign and a right-side dropdown chevron.
- Campaign Opportunities Found / Leads Found charts no longer draw distracting horizontal grid lines from Y-axis ticks.
- Bar hover text exposes the exact raw count.
- A new **Hour** grouping plots today in two-hour buckets; Day, Week and Month remain available.

## AI Requests

- Added a searchable **Task Type** filter immediately after Runtime.
- Added a sortable **Duration** column. New AI requests persist end-to-end request duration in milliseconds; the UI renders milliseconds for sub-second work and seconds otherwise.
- Migration `0031_v0843_ai_request_duration.py` adds the nullable indexed duration field. Existing historical requests remain blank when no duration was recorded.

## Lists, pagination and statistics

- Standardized bottom pagination now preserves the user's list/footer scroll position after page changes, for both client- and server-paginated views.
- Statistics adds an **Opportunities vs Leads** pie chart alongside the country charts.
- Opportunity Contact Email no longer has its own Save button; the existing note action is renamed **Save** and persists both Email and Note together.

## Local-model routing and Test Selection

- Automatic Ollama routing favours the largest installed model at or below about 12B parameters; if only larger sized models exist it uses the smallest installed model rather than silently selecting the largest.
- Optimize for Local also caps normal automatic stage targets at about 12B while manual model selection remains unrestricted.
- Automatic model resolution used by Test Selection now follows the same production routing path.
- Local compatibility-test timeouts are size-aware and longer than cloud timeouts.
- A timeout is stored as a **timeout / too slow** warning, not a hard incompatibility failure. Timing and the exact reason remain visible in stage details.
- Pipeline test schema is bumped so older validation badges do not masquerade as current 0.8.43 results.

## Recycle Bin and Blacklist

- Recycle Bin search submits automatically after a short debounce; the explicit Search button is removed.
- Added an Item Type filter for Campaign, Opportunity, Hidden Lead, Application and Outreach.
- Item Type uses the same visual Application/Outreach icons as the Applications & Outreach screen plus consistent icons for the other recycled record types.
- Blacklist Scope now uses clearer icons; **Always** is represented as a combined Opportunities + Hidden Leads scope and explained by tooltip.

## Test Discovery

- Test Discovery now starts with a required keyword field (3–240 characters), followed by the Search Engine selector and Run Test action.
- In Source-Guided mode the diagnostic runs the exact entered keyword against only the selected configured engine.
- Existing provider health/status and recent request/result statistics remain visible, and the default still favours a configured engine with recent successful results.
- Run-history search/Rows/export clutter is removed from the popup.
- The popup shows the latest 50 Test Discovery runs under **Recent Test Runs**.
- Discovery Summary includes the test keyword together with provider, queries, stages, results and errors.

## Compatibility

- Normal upgrade preserves `.env`, database, Redis, media, credentials and encryption keys.
- Run the normal restart/upgrade helper so Django applies migration `0031_v0843_ai_request_duration.py`.
