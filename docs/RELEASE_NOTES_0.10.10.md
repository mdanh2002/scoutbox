# ScoutBox 0.10.10

## Changes

- Manual filtering persists the current row before each AI request and the browser shows live elapsed time for that request. A request that exceeds the complete configured retry window plus safety grace is stopped and releases the manual-filter lock instead of appearing stuck forever.
- Clicking a normal table heading after Fit sorting clears the Fit sort badge/direction and removes the stale Fit sort state.
- Address Book renames **Name / Company** to **Contact**, moves phone and role into the Contact cell above the name/company, removes the standalone Phone and Role columns, and gives Summary more horizontal space.

No database migration is required.

Routine future releases increment the patch component on the 0.10.x line unless a deliberately major release is designated.
