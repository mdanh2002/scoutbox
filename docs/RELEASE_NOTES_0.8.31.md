# ScoutBox 0.8.31 release notes

ScoutBox 0.8.31 is a focused maintenance release based on day-to-day use of 0.8.30. It keeps the existing database schema and concentrates on diagnostics readability, long-running background work, campaign scheduling, email/application editing, and Opportunity discovery quality.

## Search Activity and AI Requests

Search Activity now combines provider outcome and result count in one **Result** column. Successful searches show the number of results in green, empty searches use a simple no-results glyph, and failures use a simple error glyph. These indicators have no button border/chrome. The **Downloaded** column is narrower so the query column has more useful space.

The AI Requests table uses explicit fixed columns to avoid header/body drift. Its detail popup renders request metadata as compact point-form rows rather than a long dot-separated sentence. **Input tokens** is shown directly below Input and **Output tokens** directly below Output.

## Campaign creation and long-running template generation

Choosing a campaign template now pre-populates the editable campaign name with a short time-based uniqueness prefix, for example `[20AUG-1337] - PROFILE - WRITER`. The prefix is a UI convenience only; users can replace the name before saving.

Candidate Profile campaign-template generation now restores an existing queued/running generation job when the page is revisited. The Generate Campaign Templates button resumes polling that job and continues showing message/progress until it finishes.

Campaign **Next Run** calculation no longer clamps an overdue due-time to the current clock time. This stops the UI from making the next run appear to move forward on every refresh while another background task delays execution. The scheduler only updates `last_discovery_run` when it actually queues a campaign run.

## Email/application editing

HTML email mode now exposes a small built-in editor with bold, italic, underline, list and link controls. Spellcheck is enabled in both HTML and plain-text modes. Switching from HTML to plain text requires confirmation because formatting will be discarded.

Signature cleanup removes `[Your Position]`. `[Your Contact Information]` is replaced with the Candidate Profile phone number when available, otherwise the application email, and bracketed candidate-name signatures are normalized to the plain name. The same cleanup is applied to tailored Hidden Lead email drafts.

The duplicate `Historical email body loaded. Save Draft when ready.` message at the bottom of the composer is removed, preventing toolbar/button misalignment. History **View** and **Use body** controls use neutral, non-pressed styling.

The Internal Development mailbox **Populate test email** action now creates matching `MailEvent` rows, so the generated inbox/draft/sent samples also appear in Email History.

## Country editing and list polish

Country can now be edited from Opportunity details and Hidden Lead details using a country selector that displays flags. Application and Outreach entry/edit forms use the same country/flag format and validate values against the configured country list.

Opportunity list-view company names are italicized. Hidden Leads displays the company domain directly below the company name, vertically centers that combined cell, removes the old empty second row, and no longer exposes the raw `Filtered: {...}` scan diagnostics blob.

The obsolete **Reject clearly incompatible geography** checkbox is removed from Candidate Scope and hard-geography rejection is disabled in enrichment. Geographic compatibility remains part of the normal fit-score/AI/heuristic evaluation instead of being a separate hard rejection.

## Notifications and diagnostics navigation

The discovery notification popup now merges Opportunity and Hidden Lead recents, sorts them globally newest-first, and shows up to ten items instead of three. Diagnostics navigation uses shorter operational names: **Search Activity**, **AI Requests**, **Audit Trail**, and **Email History** under **Diagnostics**.

## Background task cancellation

Dashboard/ScoutBox Activity rows for non-campaign `BackgroundJob` work now include a small borderless stop icon to the right of Running status. The stop endpoint revokes the Celery task when possible, marks the job `stopped`, and protects that state from being overwritten by late worker completion/failure callbacks. Campaign runs continue to use their existing campaign controls and do not expose this generic stop action.

## Opportunity discovery from job aggregators

Multi-job listing pages are no longer treated as one giant Opportunity. ScoutBox first fetches aggregator/list pages, identifies individual job-detail links and compact job-card snippets, and feeds those children into normal consolidation and Opportunity analysis. Known external ATS destinations such as Greenhouse, Lever, Ashby, Workday, SmartRecruiters and Workable are permitted when discovered from a listing page.

Direct single-role URLs on aggregator domains are still eligible. A page that remains a multi-role listing after fetch is rejected before persistence. This allows pages such as Indeed job lists and similar aggregators to contribute individual roles without dumping the entire listing page into the ranking/enrichment pipeline as noise.

## Resource charts

The Resource Usage page no longer shows the `120-min window` label. Dashboard resource behavior is unchanged. Search Provider Performance retains its concentric request/result/error rings and legend but no longer prints total requests, results and errors in the center of the chart.

## Verification

`verify_release.sh` retains the inherited v0.8.28, v0.8.29 and v0.8.30 regression suites and adds `scripts/regression_v0831.py`. The new suite covers the compact Search Activity states, AI Request popup/token layout, campaign name/progress behavior, email HTML/plain editing and signature cleanup, country selectors, test Email History population, navigation/notification cleanup, disabled hard-geography rejection, Hidden Leads/domain/list polish, scheduler behavior, aggregator expansion, background job stopping, Resource Usage cleanup, and removal of Search Provider Performance center totals.

No database schema change is required for 0.8.31; it upgrades from the existing 0.8.30 migration state.
