# ScoutBox 0.10.114

This release tightens location fidelity and list presentation after the 0.10.113 repairs.

## Fixed

- Preserves Jobicy recruiter/source role locations such as `Europe, Ukraine` and `USA, Europe` instead of expanding regions into country lists for the visible Opportunity row.
- Blocks `Worldwide`, `Global`, `Anywhere`, and related phrases from persisted locations across Opportunities, Hidden Leads, Address Book, and company/contact locations. Raw evidence can still mention those words, but they no longer become location values.
- Repairs existing expanded/corrupted Jobicy location rows by re-reading the exact source page where possible and by separating source display labels from internal location metadata.
- Rebuilds Focus taxonomy independently for Opportunities, Hidden Leads, and Address Book, so opportunity role labels are not reused as company/contact groups.
- Keeps the fresh age bucket as `< 3 days`.
- Restores `Evergreen` as a visible Post Age value when retained evidence classifies a role as evergreen, even if date evidence also exists.
- Normalizes toolbar heights across Opportunities, Hidden Leads, and Address Book so country/read/item dropdowns align with the rest of the toolbar.

## Data repair

Startup migration `0134` runs source-location, Worldwide-location, and independent Focus repair. Migration `0135` restores Evergreen as the stored/displayed Post Age value for affected Opportunities.
