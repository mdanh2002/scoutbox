# ScoutBox 0.8.30

ScoutBox 0.8.30 is a discovery-quality, application-preparation, diagnostics, and interface-hardening release. It follows the 0.8.29 campaign-history work with fixes driven by rendered UI testing of Campaigns, Hidden Leads, Applications & Outreach, Search Sources, GPT Log, and the top-right activity popovers.

## Campaign creation and editing

Selecting a New Campaign template now pre-populates the campaign name from the selected template, adding a numeric suffix when that name already exists. New campaigns enable scheduled runs by default. The code-defined **CV Discovery** starter remains available even after Maintenance cleanup and now explains that selecting it creates a normal scheduled resume/profile-driven campaign. Its technical criteria use the complete deduplicated set of Resume/Candidate Profile technical keywords rather than an arbitrary short slice.

Generated profile campaign templates likewise retain all evidence-backed technical keywords while still putting role-relevant terms first. On Campaign Detail, **Save Campaign** is on the main top action row; the obsolete Rerun/Modify path is removed because Duplicate already provides a safe editable copy workflow.

## Opportunity discovery quality

Source-guided Opportunity discovery now samples up to four search providers per campaign pass. Public Google and Brave adapters have fallback parsing anchored on result headings rather than relying on a single fragile wrapper class, improving resilience to search-result markup changes.

Known multi-employer job aggregators are treated as discovery noise rather than authoritative Opportunity pages. ScoutBox skips those aggregate hosts instead of persisting giant multi-job result pages as one role; direct employer and ATS pages remain the preferred targets. Existing aggregate-page expansion still handles useful same-site child role links where appropriate.

Opportunity country inference continues to use the shared Hidden Leads logic introduced in 0.8.29.

## Top-right discovery and campaign popovers

The discovery notification popover still counts only unread Opportunities plus Hidden Leads and reserves recent-row visibility for both categories when both have unread items. The popover can now be pinned open by clicking the icon, so it does not disappear while moving the pointer into the menu; outside click or Escape closes it.

The status popover adds a compact **Latest campaigns** section with up to five campaigns and state-aware timestamps. Running/queued/stopping campaigns show their active state, scheduled campaigns show the next run, and paused campaigns show their latest update time. The existing concrete “Next search scheduled for …” idle status remains.

## Hidden Leads cleanup and blacklist enforcement

Hidden Leads Company cells no longer show the redundant domain line beneath the company name. The website control is now a plain blue external-arrow glyph at the right-middle of the cell with no button border, square, circle, or other chrome. Clicking the company name continues to open the detail/edit view.

Latest Scan Details keeps its useful result/provider/filter summary but no longer exposes the large raw provider error/result payload in the normal Hidden Leads UI.

Blacklist matching is explicitly enforced for Hidden Leads at the domain-and-subdomain level: a blacklist entry such as `amazon.com` also suppresses `aws.amazon.com`, `jobs.amazon.com`, and other subdomains. The campaign role-gate path now rechecks the Hidden-Leads blacklist before converting a rejected role page into a company lead, closing a bypass that could previously surface blacklisted companies through campaign discovery.

## Applications & Outreach and preparation queue

Applications & Outreach now surfaces queued/running preparation work at the top of the tracker. Opportunity detail prevents a second preparation job from being queued for the same Opportunity while one is already queued or running; the Apply action is replaced by the current preparation state until that job finishes.

The Email & Application toolbar keeps **Delete IMAP Draft** immediately to the left of **Save Draft**. Saving the ScoutBox record is now treated separately from IMAP queue submission: if the database save succeeds but the worker/broker cannot accept the IMAP update, ScoutBox reports the record as saved and reports the IMAP queue failure separately instead of presenting the entire Save Draft operation as failed.

Tailoring, Resume/Cover preparation, and Application Question history is rendered beneath the action/job that produced it. New records use explicit job IDs; older history without those IDs is paired conservatively with the matching action type so legacy results are not all dumped at the bottom of the history panel.

## Email generation quality

Application/outreach email generation now uses active Resume text as first-class evidence. The prompt requires a brief, concrete 120–190 word message, a company-name greeting, no generic “I hope this message finds you well” filler, no invented experience, and no bracket/example/TODO placeholders. It asks for only a few role-relevant Resume facts rather than a generic skills inventory.

`Dear [Recipient/contact name],` and related recipient placeholders are now resolved to the company name for application emails. Candidate name, phone, application email, and portfolio use the configured Candidate Profile values. A cleanup pass removes legacy instructional placeholders such as “[Briefly describe …]” or “[mention specific tools]” when older drafts are reopened/saved.

The Candidate Profile Phone Number input keeps the 0.8.29 validation rules but now consistently uses the same dark input styling as the rest of the form instead of the browser's white telephone-input default.

## Company Info research

Opportunity detail now automatically queues Company Info research when a company is known but no useful company facts have been collected and there has not been a recent research attempt. Company research uses configured public search providers to gather evidence and the configured AI route to summarize only evidence-supported facts, then persists the research on the Opportunity. The UI distinguishes research-in-progress from a prior attempt that produced no usable public information.

## GPT Log cleanup

GPT Log is laid out as stable operational columns: **Date**, **Task / Related**, **Runtime / Model**, **Input**, **Output**, **Input Tokens**, and **Output Tokens**. There is no separate Details column. The task/stage itself (for example `question_answers`) is the clickable detail action; the full prompt, answer, attachment metadata, runtime/model information, and errors remain available in the popup.

Input and Output are multiline-clamped rather than forcing single-line/table-width distortion. Fixed table widths, server pagination, runtime/search filters, token counts, and XLSX export remain available.

## Search-source diagnostics and Search Engine Log

Search Source diagnostics now capture the provider's raw public HTTP body even for 403/429 and similar error responses. This is important for seeing rate-limit pages, consent screens, CAPTCHAs, and other provider interstitials that previously disappeared when the HTTP adapter raised. **View raw HTML response** and the sandboxed **Show in browser** preview are available whenever raw HTML was captured, including failed tests.

The Recent Requests table receives fixed sensible column widths so query text no longer collapses one character per line.

System navigation adds a dedicated **Search Engine Log** with provider/query/outcome/result count/latency/downloaded-byte history, search/runtime-style filtering, pagination, and XLSX export. The system navigation is reorganized under **Diagnostics & Logs** for Search Engine Log, GPT Log, Audit Log, and Email Log; **Configuration** and **Logout** are grouped under the final **System** section. Ask ScoutBox's navigation inventory is updated for the new Search Engine Log and Email Log naming.

## Verification

`verify_release.sh` retains all inherited safeguards and now runs `scripts/regression_v0830.py` in addition to the v0.8.28 and v0.8.29 suites. The v0.8.30 regression suite checks campaign template/default behavior, complete CV keywords, campaign toolbar changes, Opportunity provider/parser/aggregator safeguards, pinned notification/campaign popovers, Hidden Leads blacklist/UI behavior, queued preparation protection, Save Draft failure separation, evidence-grounded email generation, history nesting, phone styling, automatic Company Info research, GPT Log structure, raw provider HTML diagnostics, and the new logging navigation.

No database schema change is required for 0.8.30; it upgrades from the existing 0.8.29 migration state.
