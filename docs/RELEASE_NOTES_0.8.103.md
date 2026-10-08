# ScoutBox 0.8.103

## Opportunity compensation

- Added structured Opportunity compensation fields for display and later filtering: salary text, currency, min/max, period, provenance type, source URL, confidence and checked-at time.
- Summary cells show a compact compensation line with a leading money marker, confidence and provenance (`Job post`, `External research`, `Market estimate`, or unknown).
- When the numeric currency/period can be compared with Engagement Preferences, compensation is visually classified as meeting, overlapping, or falling below the configured expectation. ScoutBox does not invent FX conversion when currencies differ.
- Cloud Web Discovery stores compensation returned by the same Cloud research pass used for the opportunity. No extra provider call is required during ingestion.
- Local GPU Discovery never invokes Cloud salary research. It only parses already retained JD/page evidence with deterministic regex logic and treats salary as optional enrichment, so malformed or missing pay information cannot abort a Local campaign.
- Migration `0061_v08103_salary_backfill` scans historical Opportunities using retained Cloud/JD/source evidence only. Rows with no credible compensation are marked checked and display `Salary not found`; the migration performs no network or AI requests.

## Daily digest

- Top Opportunities and Top Hidden Leads are always rendered as separate sections, capped at five each.
- When a category has no new item in the rolling previous 24 hours, ScoutBox includes up to five most recent older active records instead and clearly labels each `Discovered on ...`.
- Every digest record includes an `Open in ScoutBox` link back to the corresponding list/detail context.
- External company/source URLs and contact email addresses remain explicit readable text instead of being hidden behind generic labels.
- Company naming now attempts trusted stored company research and retained JobPosting `hiringOrganization` metadata before falling back to `Unknown company`; job boards and ATS platforms are not promoted to employer names.
- Existing activity statistics, AI route/settings, cloud-budget consumption and compact error/budget warnings remain in the digest.

## Incoming / Outgoing mail configuration

- Both Internal Development and External Mail use `Incoming` / `Outgoing` tab labels.
- Internal Development remains IMAP + SMTP only. External Mail continues to support SMTP or Resend API for outgoing mail.
- IMAP Browser is integrated at the bottom of Incoming instead of being a separate tab.
- Inbox, Drafts and Sent folder mapping is integrated into the IMAP Browser section.
- Refresh Folders and Detect folders save the currently entered Incoming credentials/mapping before connecting, avoiding the old save-then-test confusion.

## Ask ScoutBox unread answers

- Ask ScoutBox has an unread-answer badge for assistant replies that finish while the Chatbot panel is not being viewed.
- Chatbot history is synchronized from the server, so an answer that completed after the user navigated away can still produce the unread badge on return.
- Opening the panel scrolls to the newest entry and clears the badge once the latest answer is visible.

## Repeat-employer application filtering

- The configured same-company cooldown is now used as a real discovery suppression window.
- A recent same-company role is hidden unless it is both substantially different from the previous applied role and unusually high-value.
- Exact same-role applications are hidden inside the cooldown (and conservatively when the historical applied date is unknown).
- A clearly old application outside the cooldown does not permanently blacklist a company/role from future rediscovery.

## Company context and historical cleanup

- Migration `0062_v08103_company_context_backfill` reuses existing company intelligence and `CompanyResearchCache` by normalized company/domain to fill missing Opportunity, Hidden Lead and Address Book company context.
- It excludes obvious job boards, ATS platforms, social/code hosts and free-mail domains when selecting a company domain.
- Unknown Opportunity employers can be recovered from trusted stored company intelligence or retained JobPosting JSON-LD `hiringOrganization` metadata.
- Where only a credible first-party domain is known, ScoutBox creates a minimal collecting baseline and marks domain-age research for later normal company research instead of inventing an age.
- New mailbox-derived Address Book contacts reuse company summary and company intelligence from their originating Opportunity/Hidden Lead when available.

## Opportunity summary cleanup

- Cloud prompt guidance asks for a 20–30 word, maximum 50-word candidate-specific reason using actual JD technologies/responsibilities and explicitly avoids generic `fit` suffixes and unnecessary em dashes.
- Local deterministic summaries use concise punctuation such as colons/semicolons and concrete JD signals rather than repetitive dash templates.
- Migration `0063_v08103_summary_punctuation_backfill` rebuilds blank, old `... fit`, and dash-heavy Opportunity summaries from retained role/JD evidence where possible.

## Configuration and About UI

- Removed the redundant helper text below Daily digest recipient and Cloud Chatbot `Allow internet search`; the controls and behavior are unchanged.
- About architecture boxes now show small runtime hints for Django, Gunicorn, PostgreSQL, Redis and Celery versions.
- The mail architecture box shows the selected Incoming IMAP endpoint and selected Outgoing SMTP/Resend endpoint.
- Overall System Architecture heading/rule alignment is shifted to line up with the content card above.
- Apply Via icons are enlarged from 15px to 18px (120%).

## Not included

- No `Maintenance > Restart System` control is included in this release.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application files, and run the normal ScoutBox restart/upgrade flow. Migrations `0061`–`0063` are data-preserving and do not perform network/AI calls during migration.
