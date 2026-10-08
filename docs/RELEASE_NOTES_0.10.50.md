# ScoutBox 0.10.50

Focused fix for Hidden Leads and Address Book company-filter status/persistence.

## Fixed

- Added active company-filter bars to Hidden Leads and Address Book, matching Opportunities.
- Persisted Hidden Leads and Address Book company size/age filters in the user session until reset/logout.
- Made compact company-filter Reset links clear session-persisted filters and return to a clean URL.
- Ensured applying all compact company-filter buckets clears the filter instead of reusing stale session state.
- Aligned Hidden Leads and Address Book re-evaluation scopes with the visible filtered list.

No database migration is required.
