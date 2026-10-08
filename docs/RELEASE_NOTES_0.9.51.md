# ScoutBox 0.9.51

## Fixed

- Resource Usage no longer compares an all-model **Token Categories** total against a filtered **Token Usage** total.
- Added a model-scoped token/category breakdown to the Resource Usage page and live telemetry endpoint.
- Applying the model multi-select now redraws both token charts from the same provider/model selection.
- Category percentages and the centre total are recomputed after filtering; the top-seven-plus-Other category presentation is retained.
- Period/date filtering and the existing 15-second live refresh remain unchanged.

## Unchanged

- Discovery, Opportunity and Hidden Lead logic.
- AI provider/model routing.
- Token collection/accounting in `UsageMetric`; this is a display/filter propagation fix only.
- Database schema.
