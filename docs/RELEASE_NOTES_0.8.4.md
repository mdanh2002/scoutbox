# ScoutBox 0.8.4 release notes

0.8.4 is a usability, diagnostics and workflow-hardening release built on the verified 0.8.3 tree. It preserves `.env`, credentials and persistent Docker volumes during upgrade.

## Dashboard and analytics
- Dashboard activity pulse and live clock provide a visible indication of current/recent ScoutBox work without a full-page refresh.
- Opportunity-search state, running work and CPU/memory/GPU state are grouped near the top.
- Apply Now, Needs Review, Information Only, Replies Today and recent-error counters refresh in the background and drill into the matching records.
- Discovery charts support Today/Week/Month/Year views and show searches, opportunities, AI tokens and errors.
- Resource Usage and Statistics refresh live values every 30 seconds. Resource sampling is also captured on demand so a recently restarted Beat worker no longer leaves empty CPU/memory charts.
- Dashboard includes recent errors and basic host/container information.

## Navigation and layout
- Navigation is reduced to Overview, Discovery, Applications, Analytics and System.
- Campaigns replaces Targeted Campaigns; Application Drafts replaces Prepared Applications.
- Search Sources, Email Configuration, Tracking Links and AI Providers are configuration tabs rather than day-to-day sidebar items.
- Import Applied Roles is now an Applied Roles page action.
- Statistics and Resource Usage are adjacent under Analytics.
- Admin/Logout alignment, last-modified timestamp and copyright presentation were cleaned up.
- Shared icon buttons, export buttons, toolbars, list paging and action rows use consistent styling.

## Discovery quality and search providers
- Public-search request URL/query templates can be customized per provider.
- Provider Test Search accepts a keyword, shows the final request URL, parsed results and raw HTML when parsing returns zero results; zero results are shown as a warning rather than success.
- English-oriented discovery prefers English locale/result providers while preserving lower-priority non-English matches when they are genuinely relevant.
- Known media/video noise such as YouTube/YouTube Music is deterministically rejected from Opportunities; documentation/media blacklist entries are enforced and existing obvious noise is suppressed during migration.
- Target pages continue to be fetched and analyzed after search discovery rather than treating search snippets as the job/lead description.
- PDF results remain eligible but receive a relevance penalty.

## Campaigns and background work
- Query Rotation preview and save run inline without reloading the page.
- Campaign Run History separates Status, Progress and Opportunities; opportunity counts link to the matching campaign results and Reuse Criteria has an explicit Action column.
- Campaign names are required and are not silently auto-generated.
- Scheduled-run enablement is placed with the primary campaign settings.
- Existing long-running network/AI operations continue to use background jobs; Dashboard diagnostics and Performance Lab completion no longer require a full-page reload.

## Applied roles and application drafts
- Applied Roles supports master-row selection and bulk deletion; Import Applied Roles sits at the top of the page.
- Import proposals use a working master checkbox, compact bulk actions and duplicate protection.
- Import confidence uses High/Medium/Low visual bands with the raw value kept in a tooltip.
- Application Drafts supports bulk deletion.
- Applied-role editing uses aligned form fields and server-side validation.

## Email and contacts
- Email configuration contains SMTP Testing and an IMAP Browser with folder assignment, message browsing and Drafts-only deletion.
- SMTP tests accept recipient/subject/body and report results inline.
- Email History remains the central incoming/outgoing history with full sanitized HTML/plain-text viewing and SMTP/observed-sent status.
- Address Book keeps generic noreply/sales suppression, source links and domain/company fallback when a person name is unavailable.

## Tracking, AI and maintenance
- Tracking-link retrieval/generation tolerates incomplete local CA stores for the configured ToughDev site, derives suffixes from retrieved article context and shows the page title in tests.
- Tracking Links supports bulk selection/deletion and links to its configuration screen.
- AI configuration is consolidated: routing lives in Discovery, provider rows are compact, test prompts sit below model configuration, cloud providers have output token caps, and Default replaces ambiguous first-model wording.
- Performance Lab includes the production freshness/post-age algorithm and modal run details.
- Maintenance includes Clear Opportunities / Cold Contacts plus Reset Workspace Data, which removes operational/test data while preserving accounts, credentials, profile, CV/cover files, provider/email settings, audit history, blacklist and tracking configuration.

## Upgrade
Keep the existing `.env` and Docker volumes, replace the application files, then run:

```bash
chmod +x restart_scout_box.sh
./restart_scout_box.sh
```

Do not rerun the initial setup script on an existing installation.
