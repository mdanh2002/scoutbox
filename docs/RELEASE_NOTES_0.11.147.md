# ScoutBox 0.11.147 — Discovery Quality and Diagnostics

## Fixed

- Balanced Opportunity admission now requires campaign-specific evidence plus stronger confidence/relevance and fit thresholds.
- Balanced Hidden Leads now require campaign-specific evidence and a higher admission cutoff; Facebook Pages are not affected.
- Rediscovery no longer blindly attaches an existing record to every campaign that encounters it.
- Direct-source candidate qualification reserves a small fair share per attempted source, closing the post-acquisition starvation path that could hide YC results.
- SearchAPI Google Jobs receives clean job intent while geography is carried by `location`/`gl`/`hl`; generic-web `site:` operators stay on web search.
- Multilingual translated queries are normalized and cannot be issued with unbalanced quotation marks; translation success/failure is visible in discovery telemetry.
- Oversized list filter selections are persisted by POST into session-scoped short filter-state tokens before GET navigation, preventing 4094-byte request-line failures across ScoutBox list screens.
- Diagnostic exports can be narrowed to ten independent categories and show approximate uncompressed per-category and selected-total sizes for the requested time period.

## Compatibility

Legacy diagnostic export requests using `include_records` / `include_diagnostics` continue to work. Migration 0219 is an audit marker only and does not mutate retained data.
