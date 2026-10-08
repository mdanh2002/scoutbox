# ScoutBox 0.10.2

## Ask ScoutBox context correctness

- Address Book questions no longer receive a contradictory top-level `address_book: []`. They receive `address_book_status.total_records` as the authoritative count, with actual contacts in `record_index.contacts` and rich contact rows in `focus_details`.
- The prompt explicitly distinguishes Address Book contacts from Hidden Leads and forbids claiming the Address Book is empty when the authoritative count is non-zero.
- Country is included in every lightweight Opportunity, Hidden Lead and Address Book directory row.
- Explicit country queries are matched against the complete loaded workspace before compaction. `query_filter_summary` carries exact per-dataset country counts, so a bounded recency window cannot be mistaken for “no records”.
- “Companies” database questions may span both company-bearing Opportunities and Hidden Leads instead of silently selecting only one table.

## Answer and link cleanup

- Removed stock conclusions that claim fit scores prove strong alignment or merely tell the user to email/visit websites.
- Public email addresses are protected from ScoutBox record auto-linking.
- Record mention links now require token boundaries, preventing a company such as `Revers` from being linked inside the word `reverse`.
- Existing protections for Markdown links, public URLs and missing contact placeholders remain in place.

## Release numbering

Routine future releases increment the patch component: **0.10.3, 0.10.4, ...**. The 0.10.x line is retained unless a deliberately major release is designated.
