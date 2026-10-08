# ScoutBox 0.11.148 — Search Activity Language Semantics

## Fixed

- Search Activity now separates target Markets, actual Query Languages, and provider locale/request-region metadata.
- Newly issued search-provider requests persist explicit query-language code/label metadata; translated multilingual searches propagate the planned language through the real provider request.
- Provider locale no longer masquerades as query language. In particular, Naver `ko-KR` rows containing English queries remain English.
- Historical language is classified only from explicit query-language or multilingual metadata; otherwise it appears as Unknown.
- Market and Query Language filters preserve sorting, paging, date ranges, exports, and compact session-backed filter state.
- Diagnostic Export places Time period at the top, uses a shorter selector, removes the divider above totals, emphasizes individual estimates, removes estimate parentheses, and ends with a right-aligned `Total (uncompressed)` row.

## Data integrity

Migration 0220 records the release upgrade only and does not rewrite historical telemetry or discovered records.
