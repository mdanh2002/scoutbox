# ScoutBox 0.8.19 release notes

ScoutBox 0.8.19 is a focused reliability and interface patch over 0.8.18. No schema migration is required.

## Search Sources

- Fixes the actual `/sources/` safe-mode trigger: historical `SearchProviderStat.day` values are date-only, but provider error history rendered them with hour/minute/second formatting. Historical rows are now promoted to local-midnight datetimes before rendering.
- The normal Search Sources page therefore keeps the complete Sources, Preferred Sources, Custom Domains, Schedule and Facebook tabs instead of falling back to the reduced recovery screen.
- Provider request/error history remains available.

## Dashboard

- Idle activity now reads `Next campaign (<name>) will start at <timestamp>` instead of keeping the previous `due at ...: <name>` wording.
- The Recent Campaigns rows-per-page selector has extra right spacing from the card edge.

## List views and Campaign Templates

- Sort arrows are larger across sortable list views. Unsorted columns use a neutral bidirectional glyph; an actively sorted column shows a highlighted up or down arrow.
- Campaign Template list view removes the Actions column. Clicking the template name opens the existing template editor popup.
