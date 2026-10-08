# ScoutBox 0.11.78

## Regional search visibility

- Records the provider regional setting with each applicable Search Activity request.
- Displays values such as `en-GB`, `uk-en`, `ko-KR`, or `zh-CN` as compact accent text beside the provider name.
- Leaves providers without an explicit regional setting unchanged.
- Includes the regional setting in Search Activity text filtering and XLSX exports.
- Shows the latest regional provider context from the last 24 hours as a compact Dashboard Background Work link.

## Dashboard query accuracy

- Splits multi-site queries before publishing Dashboard progress.
- Ensures every visible `Searching provider: ...` status contains no more than one `site:` scope and matches the request being dispatched.
- Preserves query deduplication, request limits, result consolidation, and backend source behavior.

## Included 0.11.77 refinements

- Stable Source checklist columns, concise category headings, a merged Other Sources group, and hidden Direct badges.
- Stacked Discovery Markets selectors, compact input-anchored language autocomplete, and tightened multilingual guidance.

## Verification

- Adds regional-setting telemetry and display regressions plus a multi-site liveness/progress regression.
