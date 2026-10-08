# ScoutBox 0.10.90 release notes

## Employer identity and company research

- Added one shared job-board/ATS/discovery-platform classifier used across discovery, company research and blacklist validation.
- Prevents BuiltIn, LinkedIn, Himalayas, Indeed and similar hosts from being stored as the hiring company, including subdomain/hostname variations.
- Employer extraction prefers explicit hiring-organization/page evidence and leaves the company unknown instead of substituting the listing platform.
- Company age/location enrichment no longer treats a job-board domain or hosting-site location as employer information.
- Migration `0114_v01090_platform_identity_cleanup` automatically clears historical platform-as-company identities and contaminated company intelligence so later rediscovery/re-evaluation can refill them safely.

## Cloud Re-evaluate

- Cloud + Internet Search Re-evaluate now asks for the most likely exact direct employer/ATS vacancy URL for the same role.
- A replacement requires a specific role URL and high same-role confidence; generic careers/search pages and public job-board copies are rejected.
- The original listing URL is retained as provenance/history.
- The same grounded pass refreshes company identity/info, role location, remote status, application route and post-age evidence.
- Local re-evaluation can repair obvious platform-as-company identities from retained evidence without inventing Internet-only facts.

## Blacklist safety

- Opportunity and Hidden Lead blacklisting remain company-name-only.
- Job boards, ATS hosts and aggregators are rejected as companies even if their hostname/name varies mildly.
- With no verified company-owned domain, company names shorter than 7 characters are refused before submit; a verified company domain can anchor a legitimate short company name.
- Mixed blacklist selections report one coherent result instead of success followed by a second contradictory warning.

## Forum discovery

- Fixed forum discovery being indefinitely starved by continuous primary/local discovery activity.
- Forums still run at low priority and remain tightly bounded, but a six-hour fairness override permits a small forum acquisition pass when deep-idle never arrives.
- The recovery pass is capped to one forum source/pass and existing short forum time budgets; it does not consume normal cloud-search quota merely to force a forum run.
- Scheduler diagnostics include forum age, next eligibility and starvation-override state.

## Daily digest

- 24-hour digest now shows up to 20 Opportunities, 20 Hidden Leads and 20 Address Book entries.
- Entries are ordered remote-first, then newest within the selected window.
- Opportunity rows include discovery time, remote status, post age, fit and available company size/age/location context.
- Hidden Leads and Address Book rows include discovery time plus available remote/company/contact context.
- If a category has no new entries in the 24-hour window, the digest falls back to the latest active records and labels them as fallback/latest entries.

## Recycle Bin in list views

- Added two-state Show Deleted / Hide Deleted controls to Opportunities, Hidden Leads, Blacklist, Applications & Outreach and Address Book.
- Deleted rows are visually distinct, show `Deleted on <time> · Restore`, and restore only after confirmation.
- Bulk delete ignores rows already in the Recycle Bin and reports how many selected rows are already deleted; selecting only deleted rows does not issue another delete operation.
- Toolbar ordering was normalized, including Applications & Outreach: IMAP Sync → Import → Delete → Show Deleted → Add, and Address Book: Re-evaluate → Filter → Delete → Show Deleted → Add.
- Search fields on the affected list screens use a shorter desktop width while retaining responsive behavior.
