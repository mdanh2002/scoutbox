# ScoutBox 0.11.152 — Query Language Unknown-Facet Correction

## Fixed

- Search Activity no longer places every legacy row with missing query-language telemetry into the `Unknown` bucket.
- Rows that predate semantic query-language telemetry are treated as `unrecorded`, remain visible under `All Query Languages`, and are excluded from language-specific filtering.
- `Unknown` is reserved for explicit stored language values that cannot be normalized.
- True unknown entries display `?` in the code column, fixing the alignment of the Unknown row.
- Search Activity XLSX export distinguishes `Unknown (?)` from `Not recorded` historical telemetry.

## Why the count was so large

Semantic query-language metadata was introduced only in the 0.11.148 line. Older Search Activity records generally have no `query_language`, `query_language_label`, or `multilingual_language` value on the provider-request row. 0.11.148-0.11.151 grouped every such record into `Unknown`, so an all-time history could show hundreds of thousands of supposed unknown-language requests even though the language was simply never recorded. This release stops treating absence of old telemetry as a language classification.

## Data safety

No historical UsageMetric rows are rewritten or deleted. Migration 0224 records the release upgrade only.
