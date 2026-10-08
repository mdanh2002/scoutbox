# ScoutBox 0.11.151 — Query Language Code Normalization

## Fixed

- Search Activity no longer displays full language names such as `AZERBAIJANI` or `KHMER` in the language-code column.
- Added stable ISO 639-1 codes for every market-native language currently present in ScoutBox's global discovery catalogue.
- Historical 0.11.148-0.11.150 telemetry that stored a full language name in `metadata.query_language` is normalized at read time.
- Query Language filters match both normalized codes and legacy full-name metadata, preserving filtering across the upgrade.
- XLSX export and row badges use the same normalization logic as the filter dropdown.

## Data safety

No historical UsageMetric rows are rewritten or deleted. Migration 0223 records the release upgrade only.
