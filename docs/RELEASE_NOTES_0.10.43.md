# ScoutBox 0.10.43

Regression and data-quality release following 0.10.42.

- Campaign run history/charts now count newly-created Opportunities and Hidden Leads, while retaining rediscovery IDs separately in run diagnostics.
- Address Book `/contacts/` company-size filtering is initialized and applied correctly, fixing the 500 regression.
- Hidden Leads and Address Book use a compact filter-icon dialog for Company Size (employees), with cumulative multi-band filtering and Reset.
- Opportunity Advanced Filter company panels use the normal ScoutBox group styling and label the size unit as employees.
- Hidden Lead persistence has an explicit high-confidence adult-content gate across local, source-guided and Cloud Web paths; historical clear matches are recycled by migration 0094.
- Hidden Lead/Address Book URL-health semantics remain page-availability-only; legacy job-presence warning state is cleared for those record types. Opportunity soft-404 remains role-aware.
- Foreign-script search/browser fragments are removed from Opportunity role titles; pure non-Latin shell titles receive a safe fallback during migration.
- Async list filtering now falls back to a normal navigation if an AJAX refresh fails, so Audit Trail and other server-filtered list toolbars cannot remain visually stale.
- Campaign Detail Remote column is constrained to a compact width.
