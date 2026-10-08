# ScoutBox 0.10.87 Release Notes

## Fixes

- Opportunity status filter counts now clear queryset ordering before aggregating status facets. This prevents Django/database grouping from splitting rows by the list ordering timestamp and showing each status as `(1)`.
- Country facet aggregation now uses the same ordering-free grouping guard so grouped counts stay stable when the list queryset contains ordering or many-to-many joins.

## Upgrade notes

No manual SQL is required. This release keeps the v0.10.86 automatic aggregator blacklist recovery migration and adds a display/query fix only.
