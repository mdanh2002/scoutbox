# ScoutBox 0.11.34

Targeted UI hotfix for list multi-select filters and re-evaluation history details.

## Fixed

- Reduced Address Book Location and Focus multi-select rows to match the compact height used by Opportunities and Hidden Leads.
- Converted Campaign, Location, Focus, Provider, and Provider Type multi-select filters to deferred Apply behavior so checkbox changes do not refresh the list until Apply is clicked.
- Closing a multi-select dropdown without applying now reverts uncommitted checkbox changes.
- Added an Apply button aligned to the right of the Select all / Deselect all row in all affected multi-select dropdowns.
- Kept dropdown search fields client-side only and prevented them from refreshing the list.
- Kept icon spacing only where icons/flags are shown.
- Improved single-entry re-evaluation result tables so one result no longer stretches awkwardly across the whole detail panel.

No database migration is required.
