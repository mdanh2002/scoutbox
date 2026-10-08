# ScoutBox 0.8.73

## Cloud opportunity persistence

Cloud verification rows now use a field-preserving canonical dedupe path before ingestion. Remote/current/country/fit/Post Age fields are no longer lost by Source-Guided consolidation. Cloud Opportunities still require a specific item URL, verified remote eligibility, and no explicit closed/expired status.

## Hidden Leads

Cloud-nominated non-matches are not persisted directly. A separate Cloud Web research pass decides whether each candidate is a directly actionable outreach target. Blogs, articles, documentation/resources, ATS/job-board infrastructure, generic directories, and broad foundations/training portals without a concrete relevant intake/contact route are rejected. Kept leads include an AI-resolved country and outreach path.

## Address Book

Directly inspected Cloud URLs may yield email candidates, but those candidates are now validated in a separate Cloud pass before persistence. Example/demo/third-party addresses and privacy/GDPR/EEO/compliance/security/press/investor/noreply mailboxes are rejected. Legitimate recruiting/job inboxes can be retained. Human-looking usernames provide practical salutation names when the page does not state a person (`rachel.weiss` -> `Rachel Weiss`; `alex.m` -> `Alex M`). Company attribution uses validated ownership/domain evidence rather than blindly copying the page company. Source-Guided discovery is unchanged.

Maintenance can move Cloud Web-generated Hidden Leads and Address Book contacts to the Recycle Bin for a clean rebuild with these rules.

## UI and diagnostics

- Test Discovery remains viewable/reopenable while its background job is running.
- AI Request list previews and full popup payloads use JSON syntax highlighting, including Markdown-fenced JSON; Copy/export still use the exact stored raw payload.
- CPU, RAM & Tokens uses one 0-100 chart axis. Request/token lines are normalized only for drawing; raw current values are shown to the right and in tooltips.
- Campaign Run History includes Cloud URL/verification/lead/contact accounting.
- Discovery Method changes create an audit event.

No database migration is required for 0.8.73.
