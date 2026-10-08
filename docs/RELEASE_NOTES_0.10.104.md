# ScoutBox 0.10.104

## Focus taxonomy stability

- New Opportunities, Hidden Leads and Address Book contacts are assigned into the existing Focus taxonomy whenever an established group fits.
- Normal small background additions no longer trigger full Focus repopulation or rename/clear existing groups.
- A full rebuild is considered only for an under-populated initial corpus, substantial corpus growth, or a 30-day age threshold with meaningful growth.
- Full rebuilds are generated in shadow mappings and committed atomically only after every list receives a complete valid assignment. Local AI failure leaves the live taxonomy unchanged.
- Temporary classifier unavailability leaves a new item retryable instead of persisting `Unclassified` as a false classification.

## Post Age and list UI

- The youngest age bucket is displayed consistently as `~ 1 week`, including the Opportunity list and tooltip.
- Post Age tooltips show the approximate bucket plus the exact posted date, or estimated posted date, when available, followed by source/evidence information.
- Unknown `?` Post Age values remain tooltip-free.
- Contact-via icons are larger and more visible. Email uses a distinct outgoing-mail glyph so it cannot be confused with the direct-email icon below.
- `Hide failed URLs` now explains its behavior in Opportunities, Hidden Leads and Address Book.

## Remote / hybrid / on-site integrity

- Remote, Hybrid and On-site badges now require explicit role-level working-arrangement wording or trusted structured workplace metadata from a direct source.
- Semantic guesses such as benefit wording or phrases like `growing your career` cannot produce a Hybrid badge.
- Technical phrases such as remote access, remote systems, remote devices and remote monitoring do not count as remote-work evidence.
- Job-board SEO/collection titles containing the word remote do not count as role-level remote evidence.
- Manual metadata refreshes are prevented from overwriting the working-arrangement badge unless the retained role text independently supports the same classification.
- The one-time 0.10.104 integrity repair clears unsupported retained Remote/Hybrid/On-site classifications back to Unknown.

## Blacklist integrity

- Company blacklist matching uses conservative canonical company identity normalization, including safe legal suffix handling.
- Blacklist enforcement runs after employer identity changes, not only at initial discovery.
- A one-time upgrade repair applies active blacklist rules to retained records so companies such as a previously blacklisted Canonical cannot keep reappearing after later identity enrichment.

## Opportunity role/JD integrity

- Employer/ATS replacement URLs are independently validated against the replacement page. A semantic review of the original page can no longer validate a different replacement page.
- Generic job-board collection/search pages, application-questionnaire shells and navigation labels captured as employer names are rejected.
- If an attempted employer/ATS replacement fails but the original job-board vacancy remains valid, ScoutBox restores the original vacancy instead of keeping an unrelated page.
- The one-time 0.10.104 integrity repair revalidates suspicious retained substitutions.

## Diagnostic export period

- The selected period now applies to ScoutBox records by when they entered ScoutBox: Opportunity first-seen/date-created, Hidden Lead created date, Address Book created date, and Application date-added/created date.
- Routine `updated_at`, URL-health `last_seen`, enrichment refreshes and deletion timestamps no longer pull old records into a short-period ScoutBox Data export.
- Operational logs and diagnostics continue to use their event timestamps; current non-secret configuration remains a snapshot regardless of period.

## Includes 0.10.103 corrections

- Evidence-grounded country/location handling and one-time country repopulation for Opportunities, Hidden Leads and Address Book.
- Full-result server sorting in affected paginated list views.
- Correct `All countries` universe count.
- Compact Opportunity/Lead HTTP status badges.
- Settings helper cleanup and unknown Post Age tooltip cleanup.
- IANA-bootstrap/authoritative RDAP domain-age lookup with safe unavailable handling for registries that do not publish creation dates.
