# ScoutBox 0.8.58 release notes

ScoutBox 0.8.58 is a no-migration list-search and diagnostic-download reliability release.

## Changes

- Diagnostic export remains a ZIP containing the anonymized JSON snapshot, but the export dialog now closes before transfer begins and the browser handles the attachment in a hidden download target. The previous JavaScript `fetch()`/Blob transfer path is removed.
- Configure → Maintenance restores the original page-level destructive-actions guidance.
- Server-backed list searches now update in place as the user types. Opportunities, Hidden Leads, Recycle Bin, Blacklist, Audit, Search Activity and AI Requests share the same debounced background-fetch behavior; their paging/filter controls also update without reloading the page.
- Existing local table searches continue to filter instantly in the browser. Release checks verify that list search controls are wired to either a valid local table target or the asynchronous server-list mechanism.
- Opportunity and Hidden Lead normal keyword matching is limited to visible list information; hidden URL paths are searched only for URL/domain-like queries.
- Campaign Focus previews truncate at keyword separators such as commas rather than at arbitrary word boundaries.

No database migration, new telemetry, provider-routing change, discovery scheduling change or other unrelated system behavior is included.
