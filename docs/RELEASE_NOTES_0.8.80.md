# ScoutBox 0.8.80 Release Notes

ScoutBox 0.8.80 is a reliability and review-UI release based on live 0.8.79 review.

## Blacklist enforcement

- Active blacklist rules are now applied to already-stored active Opportunities and Hidden Leads, not only to candidates during future discovery.
- The 0.8.80 migration performs a one-time reconciliation on upgrade so existing records such as a previously stored `canonical.com` Opportunity are hidden immediately when that domain is already blocked.
- Opening the Opportunity/Hidden Lead inventories defensively re-applies the active blacklist, and adding/enabling a blacklist rule applies it immediately to matching stored records.
- Matching covers target, canonical/original and search/source URLs as applicable, including subdomains and path-scoped blacklist entries.
- The Blacklist page's missing `get_item` template filter is restored, fixing the `/blacklist/` 500 error.

## Review UI and diagnostics

- Hidden Lead HTTP health is a small intrinsic badge directly after the company name with normal spacing from the external-link icon.
- `Older / uncertain` Post Age uses an archive icon with the label beneath it; queued Campaign status is no longer green.
- The stray resource-chart `%` label is removed.
- Campaign/Background activity on Dashboard shows its start timestamp; Recent Errors shows the unread count and highlights new error rows.
- Campaign list rows expose their generated ID, Opportunity Fit is compact, and Post Age info/refresh actions have clearer spacing.

## AI Requests and Ask ScoutBox

- Ask ScoutBox can export the current transcript to XLSX from the chat header.
- Chat Markdown headings render as compact bold text and excessive blank-line spacing is reduced.
- Chat context now includes a streamlined view of Address Book, configuration, recent errors, notifications and recent Campaigns in addition to Candidate Profile, Opportunities, Hidden Leads, Applications/Outreach and recent conversation.
- AI Requests hides the separate Attachments column and shows attachment filename/size beneath Input and in the detail dialog.
- Page-summary tasks retry once when a substantive source receives an obviously incomplete response; both attempts remain visible in AI Requests.

## Routing and configuration cleanup

- Company research performed while Cloud Web is selected remains on the configured Cloud route instead of silently invoking Source-Guided/local search providers.
- Search Sources removes the misleading Cloud-Web source-choice notice and places shared schedule guidance directly beneath the Schedule heading.
