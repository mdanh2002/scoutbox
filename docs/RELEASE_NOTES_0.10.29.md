# ScoutBox 0.10.29

0.10.29 is a regression hotfix for the Opportunities advanced filter and Hidden Leads list introduced in the 0.10.27/0.10.28 feature set.

- Fixes an Opportunities HTTP 500 caused by applying `only()` to a QuerySet that still carried `select_related(source, application, origin_campaign)` while evaluating advanced filter buckets.
- Fixes a Hidden Leads HTTP 500 caused by the same Django deferred-field/select-related conflict in the noisy-host probe after `origin_campaign` was added.
- The temporary filter/probe QuerySets now explicitly drop joined/prefetched relations before selecting only the fields they need.
- Opportunity advanced-filter groups default to all checked when unrestricted.
- Previously applied advanced-filter selections are restored when the Filter dialog is reopened.
- The modal Reset button is only shown when a real advanced filter is active.
- Apply Filter is disabled if a filter group has no selected values, avoiding an invalid/ambiguous filter state.
- Fixes Post Age over-aging when a page/item update timestamp or HTTP `Last-Modified` date is much older than the actual job posting. Update/modified dates are now audit/supporting evidence only and cannot create or widen Post Age.
- Freshness prompts now prioritize explicit posting dates and role-specific relative phrases such as `4 months ago`; Cloud discovery/re-evaluation is explicitly forbidden from using page-update metadata as `posted_date`.
- Selecting every value in a group is normalized to unrestricted, so it does not produce redundant query parameters or misleading active-filter text.
- No database migration is added; 0.10.28 migration sequencing remains unchanged.

Routine future releases increment the patch component.
