# ScoutBox 0.8.18 release notes

ScoutBox 0.8.18 is a quality and consistency upgrade over 0.8.17. It preserves existing data and configuration while adding migration 0016 for Market Studies/query cleanup.

## Search Sources and discovery

- `/sources/` is protected by layered fail-soft rendering, including an independent safe-mode view and last-resort HTTP 200 diagnostics response.
- Search-provider request/error history remains available in provider popups.
- Saved campaigns, templates, run payloads, background results, usage metadata, performance tests and saved filters are re-scrubbed for legacy `generic full stack` and unary `-...` provider clauses; suitability exclusions remain an internal post-fetch concern.
- Search activity text no longer wraps an already quoted search phrase in another pair of quotes.

## Market Studies

- Known forums, publishers, editorial communities and documentation/reference hosts are rejected as company leads, including XDA Developers and Hackaday-style false positives.
- Company inference prefers registrable domains, academic/institutional identity and page branding instead of the first subdomain label.
- Country inference can use target-page text and domain signals; unknown country remains blank.
- Summaries are grounded in page/homepage evidence, omit the already-visible company name, avoid keyword-list claims, and target one or two useful sentences around 35–60 words. Existing rows are rebuilt during migration where evidence supports a summary.
- The grid keeps summaries on one visual line, removes the grid-level outreach action, and the detail popup keeps only the Prepare Outreach action plus bounded Extracted Text.

## Dashboard and diagnostics

- ScoutBox Activity shows active work only; when idle it reports the next due campaign instead of retaining old telemetry such as completed chatbot analysis.
- Host architecture/CPU-count strings are removed from the activity strip. Diagnostics shows Host OS, RAM, CPU, Storage and GPU one fact per row.
- First Run Readiness uses real Incoming/Outgoing mailbox endpoints and normalized Resume/Cover Letter wording.
- Summary metrics share the same card background, error values/icons use light red, and the other icons inherit the same accent as their number.
- Recent Campaigns supports rows-per-page and paging.

## Campaigns and list views

- Campaign names, Campaign Template names and Blacklist domains are no longer bold by default.
- Location is hidden from Campaign and Campaign Template list views but retained in editors/details.
- Campaign Templates show Created and Last Updated.
- Campaign Status remains a link to details but uses plain state glyphs: clock for Scheduled, activity glyph for Running and pause-state glyph for Paused, with no enclosing button shape.
- Practical list-table columns gain working sort behavior; selection/action columns remain unsortable.

## Applications, profile and terminology

- Applied-role import is titled Import Applied Roles. Application document types are shown on one line; mailbox scan results are one folder per line; Sync Mailbox is aligned with Add All.
- Application Drafts hide placeholder company text and show Created plus Last Updated.
- Address Book hides Confidence.
- Candidate Profile places Preferred language directly below Operating locations and removes the redundant default-language helper.
- User-facing CV terminology is standardized on Resume/Resumes and Cover Letters without changing the backwards-compatible internal `kind='cv'` value.
- Resume/Cover Letter deletion uses an in-app confirmation that names the selected document.
- Engagement Preference checkboxes flow left-to-right and wrap naturally; Hiring-process guidance is grouped with Location & engagement.
- About ScoutBox uses a graphical six-step Discover → Validate → Analyse → Review → Prepare → Track workflow.

## AI/model status

- Ollama diagnostics display installed model count without a confusing `loaded` count that does not represent model usability.
