# ScoutBox 0.8.34 release notes

ScoutBox 0.8.34 is a focused reliability and workflow follow-up to 0.8.33. It completes the Recycle Bin lifecycle for Hidden Leads, hardens credential-free Google testing against bot/rate-limit behavior, makes Company Info visibly useful while background research runs, rejects multi-job aggregator listing pages as opportunities, keeps standalone list controls visible during scrolling, and removes the empty attachment placeholder from AI Requests.

## Hidden Leads in Recycle Bin

- Deleting selected Hidden Leads now moves them to **System → Recycle Bin** instead of physically deleting them immediately.
- Recycled Hidden Leads appear with the same simple fields as the other item types: Date Deleted, Item Title, Item Type, and Restore.
- Restore returns the Hidden Lead to the active list and marks it read.
- Empty Recycle Bin permanently removes recycled Hidden Leads together with other recycled records.
- While a Hidden Lead remains in the Recycle Bin, both Hidden Leads scans and campaign lead capture suppress matching companies/domains. After the bin is emptied, a later scan/campaign may discover the lead again.
- Background lead refinement/drafting tasks no longer pick up a lead after it has been recycled.

## Google public search

- Credential-free Google requests now use `curl_cffi` browser impersonation when available so the TLS/client fingerprint matches a real Chrome-family browser more closely than Python `requests`.
- Public Google calls are globally paced and successful query results are cached for ten minutes to reduce repeated requests that can trigger HTTP 429 responses.
- The old rapid domain/URL retry behavior is not used after Google returns a block/interstitial.
- The Search Source test form no longer follows a failed Google test with a second raw-preview request, which previously doubled traffic and could deepen a rate limit.
- A 429/interstitial failure now reports a concise ScoutBox message rather than exposing Google's very long `/sorry/` redirect URL.
- Programmable Search credentials remain optional; when configured they still provide the most deterministic Google API path.
- The release adds `curl_cffi>=0.15,<0.17`; the normal upgrade/restart rebuild installs it automatically.

## Company Info research

- Opening an opportunity with a known company immediately persists a small Company/Location baseline, so Company Info does not remain an entirely blank “Collecting…” card while a worker is busy.
- Company research now uses all enabled supported search adapters instead of requiring a potentially stale `adapter_status=active` label.
- AI synthesis is routed through the configured **Company Enrichment** stage.
- Existing first-party opportunity evidence and the company root page are used when available.
- If search providers or AI are unavailable, ScoutBox keeps a concise evidence-based fallback instead of discarding all useful company information.
- The Company Info card polls its background job and refreshes itself when the research completes.

## Aggregate job-list pages

- Known job-board collection URLs are not eligible to become one Opportunity, even when the page has one selected job or one `JobPosting` schema in a side panel.
- In particular, Indeed URLs such as `q-<role>-l-<location>-jobs.html?vjk=<id>` are treated as a search/list page. The `vjk` selection is not treated as proof that the URL is a single job detail page.
- Collection expansion strips selection-only parameters before extracting child job links. Only individual role/detail URLs proceed through normal validation and enrichment.
- The detector also covers common LinkedIn/Glassdoor collection paths and localized Indeed/Glassdoor domains.
- Migration `0029_v0834_lead_recycle.py` suppresses existing recognized aggregate-list Opportunities while retaining any linked Application record/history.

## List-view usability

- Primary toolbars on standalone list pages are sticky below the global top bar, keeping search, action buttons, export, and Rows-per-page controls accessible while scrolling.
- Applied to Opportunities, Hidden Leads, Applications & Outreach, Campaigns, Blacklist, Audit Log, Search Activity, AI Requests, Recycle Bin, and Email History list panels.

## AI Requests

- An empty Attachments cell is now genuinely empty instead of showing a dash.
- The request-detail modal also leaves the attachment line empty when no files were attached.

## Upgrade notes

Keep the existing `.env` and Docker volumes, replace the application files, then run `./restart_scout_box.sh`. The restart helper rebuilds the image (including the new browser transport dependency) and applies migration `0029_v0834_lead_recycle.py` without deleting persistent data.
