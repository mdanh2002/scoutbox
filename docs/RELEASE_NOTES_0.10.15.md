# ScoutBox 0.10.15 release notes

ScoutBox 0.10.15 is a migration-free re-evaluation and Address Book correctness/UI release.

- Re-evaluation uses a single global active-run lock across Opportunities, Hidden Leads and Address Book.
- If nothing is selected, the user can choose **All Items**, **Local AI Only**, or **Cancel**. The Local AI scope also includes legacy assessments whose provenance is not cloud-grounded.
- Address Book has the same live re-evaluation status treatment as Opportunities and Hidden Leads.
- New Address Book contacts are Fit-assessed before persistence with the configured default discovery route; an unavailable/failed assessment does not render a misleading `00` badge.
- Address Book locations are canonicalized to country-only list display so country flags remain useful when imported data contains city/region detail.
- Resource Usage current-value metrics are again rendered as a compact single left-to-right strip.

No database migration is required.

Routine future releases increment the patch component on the 0.10.x line unless a release is deliberately designated as major.
