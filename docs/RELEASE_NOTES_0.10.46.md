# ScoutBox 0.10.46

0.10.46 is a focused repair release for the company-filter toolbar and threshold checkbox behavior.

## Fixed

- Hidden Leads and Address Book now expose an always-visible icon-only Company filter action in the toolbar.
- The compact Company filter dialogs include Company Size (employees) and Company / Domain Age.
- Opportunity, Hidden Leads, and Address Book threshold filters now cascade consistently: checking a wider threshold checks all narrower thresholds, and unchecking a narrower threshold unchecks wider thresholds.
- Unknown / Others remains independent of threshold cascading.

## Upgrade

No new database migration is required beyond the 0.10.45 migration set. Replace the application files and restart ScoutBox.
