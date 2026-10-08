# ScoutBox 0.8.87

ScoutBox 0.8.87 is a reliability, discovery, reporting and UI release based on 0.8.86.

## Discovery and record durability

- Cloud AI Discovery now treats enabled Custom Domains as explicit cloud research targets and can fall back to direct page retrieval plus Cloud analysis without routing through Local Search Sources or Ollama.
- Verified direct employer role pages are preferred over third-party listings while preserving discovery provenance.
- Local GPU search-engine queries are normalized immediately before provider requests: Boolean filler is removed and no outgoing request can contain more than three quoted words in total.
- Persisted Local GPU Opportunities and Hidden Leads are no longer automatically deleted/recycled by duplicate reconciliation, overlap handling, list rendering or late qualification. Records flagged by qualification are retained for review.
- Automatically collected Address Book entries are append/update-only; automatic contact quality reconciliation no longer retires a visible contact.
- Future automatic contact assignment rejects disability/accommodation, privacy/GDPR/data-request, legal/compliance, terms, abuse/security and similar administrative mailboxes. Existing stored entries are not retroactively changed.

## Limits, reporting and diagnostics

- New Cloud defaults: 100 deep-research candidates/run, 250 page recoveries/day, 5 automatic runs/campaign/day, 240-minute minimum automatic interval, 1,000 Cloud requests/day, 3,000,000 input tokens/day and 1,000,000 output/reasoning tokens/day.
- 50%, 80% and reached/exceeded usage notifications are deduplicated per accounting period and sent both in ScoutBox and through configured notification SMTP.
- Analytics `Today` is replaced with a genuine rolling `Last 24 hours` window on Dashboard, Resource Usage and Statistics.
- Daily Digest is rebuilt as a structured rolling-24-hour report covering Opportunities, Hidden Leads, Application/Outreach status changes, major errors, Schedule/Limits and Resource Usage. General settings include `Send Test Digest Email`.
- Maintenance diagnostics exports include persisted Chatbot history.

## Candidate profile and templates

- Resumes display the most recent Campaign Template generation time and generated templates retain a secondary original-resume download while that Resume exists.
- Resume and Campaign Template lifecycles are independent; regeneration replaces the linked generated template without altering existing Campaigns.
- Bulk `Auto-create Campaign Templates` processes all Resumes and never creates or modifies actual Campaign records.
- State-changing Resume/Template actions have explicit consequence confirmations.

## Company, URL and Address Book data

- Company Info preserves employee-count/size evidence and displays it in the tooltip.
- When company founding information is unavailable, RDAP domain-registration age can be shown explicitly as `Domain Age` with a distinct domain-age icon; it is never represented as company age.
- Passive HTTP health badges tolerate certificate-validation failures only for reachability probing. TLS verification for authenticated/SMTP/AI/other requests is unchanged.
- Address Book displays a domain HTTP-health badge next to the email address.
- Raw Opportunity text uses actual retrieved page content and exposes the retrieval failure when source text is unavailable.

## Chat and UI

- Ask ScoutBox persists the user turn before AI execution, keeps the message in local transcript history, always clears/restarts the request queue after failures/timeouts, shows typing while active and emits record-level detail links using real ScoutBox IDs.
- CPU, RAM & Tokens refreshes every 15 seconds, draws a vertical dashed timestamp guide on hover, and removes the redundant right-edge x-axis timestamp.
- Opportunities footer aligns Rows/Export left and count/pagination right on one responsive row.
- Dashboard Recent Campaigns spans the full available width; the latest-error chip no longer repeats a `Latest error:` prefix.
- Resumes place Delete after Generate Template for action alignment.
- Seen/read main-list rows now receive a mild hover state while new/unseen rows retain a stronger distinct hover.
- A Campaign in `stopping` state cannot be resumed/enabled until the active run has finished stopping, both in the UI and backend.
- About ScoutBox includes a balanced software-engineering `Overall System Architecture` section.
