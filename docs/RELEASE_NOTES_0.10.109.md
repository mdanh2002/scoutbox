# ScoutBox 0.10.109

## Fixed

- Unclassified filter bug fixed: selecting Unclassified now returns blank and explicit Unclassified rows.
- Focus repair now runs on upgrade to reduce excessive Unclassified rows, suppress broken labels such as Would Useful, and rebalance Opportunities, Hidden Leads and Address Book independently.
- Focus filtering now treats the visible `Unclassified` option as blank plus explicit Unclassified, so selecting it returns the matching records instead of an empty list.
- Focus grouping now uses stronger topic rules and balanced batch assignment to reduce huge unclassified buckets while avoiding one-item or overly generic labels.
- Weak labels such as Writing, Would Useful, C++, Protocol Reverse, Security TLS, Embedded, Firmware and Application Engineer are rejected or rewritten to useful technical groups where supported.
- Opportunities, Hidden Leads and Address Book keep independent Focus namespaces and repair their labels independently.
- Random prose fragments are rejected as company names, and an upgrade repair clears existing sentence-fragment company values.
- Search inputs in Opportunities, Hidden Leads, Address Book, Blacklist and similar list toolbars now match dropdown height.
- Address Book footer controls are moved down to avoid crowding/overlap with the table.

## Verification

- Python syntax/AST checks.
- Targeted 0.10.109 static regression checks.
- Compose YAML and shell syntax checks where tools are available.
