# ScoutBox 0.8.96

## Changes since 0.8.95

- Reworked Opportunity list highlights into short natural "why this is interesting" phrases/sentences instead of keyword lists. The upgrade migration repopulates all existing Opportunity highlights from retained evidence.
- Updated Cloud Web and local AI classification prompts so future highlights are candidate-relevant, evidence-backed, natural language and at most 50 words.
- Moved the Hidden Lead external/open icon to the end of the Summary line and narrowed the Company column.
- Narrowed the Opportunity Role / Company column to give Summary more room.
- Added Last 7 days, Last 2 weeks and Last 30 days to Diagnostic Data export periods.
- Added Last 2 weeks to Rebuild Missing AI Data periods.
- Async list toolbars now refresh filter options/counts after filtering. Search Activity and AI Requests therefore show counts scoped to the other selected filters rather than stale global values.
- Opportunity and Hidden Lead campaign/country/read/status counts are now faceted against the other active filters.
