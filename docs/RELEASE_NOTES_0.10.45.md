# ScoutBox 0.10.45

0.10.45 repairs release-blocking issues found after 0.10.44 and tightens the related regression checks.

## Fixes

- Fixed async list URL construction so Audit Trail and other list filters cannot navigate to `[object HTMLSelectElement]` when a form contains controls named `action`.
- Made the Hidden Leads and Address Book company filters visible in the toolbar and included both Company Size (employees) and Company / Domain Age in their compact dialogs.
- Aligned company size and age checkbox choices in columns across filter dialogs.
- Reworked diagnostic export ZIP filenames to avoid duplicate wording, reflect selected record/log content, and include HHMMSS in the from/to range timestamps.
- Added a deterministic job-presence guard for valid Wellfound/AngelList job descriptions so active postings are not incorrectly flagged as soft-404/no-role pages.
- Expanded opportunity-title cleanup for scraped search/JD sentences, including `Senior Security Researcher at Company` and `Looking for experienced programmer ...` patterns.
- Prevented job boards and ATS/platform hosts such as JobsDB, LinkedIn, Wellfound, Workday, Lever, Greenhouse, and similar sources from being used as the company identity for size/age decisions.
- Historical cleanup migration clears platform-derived Company Info and leaves records unknown when no real company is available.

## Upgrade notes

Run migrations through `0096_v01045_release_repair` after deploying this package. Existing `.env` files and Docker volumes are unchanged.
