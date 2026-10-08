# ScoutBox 0.10.94

## Scheduler and worker reliability

- Serializes scheduler decisions across processes with a Redis ownership lease and a database row-lock claim fallback.
- Prevents duplicate scheduler work from simultaneous ticks and retains one-at-a-time Forum launch protection.
- Records scheduler gap/worker-inspection health and an audit warning when the scheduler resumes after a prolonged silence.
- Recovery requeues interrupted company-research jobs centrally rather than requiring an Opportunity page to be opened.
- Recovery resumes current due work; it does not replay every missed Forum interval.

## Forum acquisition

- Normal Forum acquisition cadence is five minutes (`SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES=5`, global interval five minutes).
- Each bounded Forum pass can fail over across up to three sources inside the existing short HTTP stage budget.
- A successful HTTP request that yields zero useful candidates no longer ends the pass.
- Source cooldown distinguishes persistent access denial, rate limiting, parsing failures and repeated transient network failures.
- Five-minute source rotation and retained source-efficiency statistics favor healthy productive communities without unbounded crawling.
- Forum acquisition stays on the dedicated one-slot Forum worker. AI-backed qualification yields to active primary discovery/background AI work.

## Opportunity and employer integrity

- Adds a non-overridable source-integrity gate for serialized job datasets, GitHub Gists containing harvested job records, structured data dumps and search-result/listing dumps.
- Rejects malformed titles containing serialized fields or large description/data fragments before persistence.
- Tightens company-name plausibility and deterministic recovery from strong page/aggregator wording such as `Ashby is hiring…` and `About the Role OpenAI`.
- Upgrade migration recycles obvious pre-existing dataset/Gist Opportunities and repairs deterministic malformed/blank employer identities using stored evidence only; no cloud-AI migration calls are made.
- Employer identity remains independent of asynchronous Company Info research.

## Company Info

- Interrupted Company Info jobs are requeued on worker recovery and duplicate recovery jobs are suppressed.
- Existing company/domain research cache continues to be reused across records.
- The existing Company Info icon is unchanged.
- Its tooltip now includes two additional lines whenever resolved: `Domain: example.com` and `Domain age: 15 years`, even when company age/employee size are already available.
- Unknown Company Info badges expose lifecycle state such as Queued, Researching, Research failed or Unavailable instead of one unexplained state.
- Legacy company-intelligence rows are marked eligible for domain-age refresh where stored domain evidence exists.

## Email delivery diagnostics

- Outgoing Resend/SMTP submission is recorded as `Accepted`, not `Delivered`.
- Resend provider IDs are stored/displayed and recent accepted messages are refreshed against provider delivery status when possible.
- Email History distinguishes Accepted, Delivered, Bounced/Rejected/Failed, and IMAP-observed Sent states.
- Scheduled digest metadata records intended schedule time, actual submission time and recovery delay.
- Manual Daily Digest and outgoing tests report provider acceptance and message ID rather than implying inbox delivery.
- Digest content limits are unchanged.

## Detailed log retention and Resource Usage

- Adds **Config → General → Keep detailed logs for**, 14–180 days, default 90.
- Automatic retention removes detailed operational telemetry only; Opportunities, Hidden Leads, Address Book, Applications/Outreach, campaigns/templates, Candidate Profile and other business records are not retention targets.
- Search-provider aggregate statistics are preserved by both scheduled retention and manual Clear Logs.
- Resource samples follow the configured retention period; the 15-second sampler no longer performs cleanup.
- Retention cleanup runs as a daily bounded task.
- Long Resource Usage ranges use adaptive buckets rather than daily averages. 30-day views retain intraday resolution and All Data uses all retained samples.
- Resource buckets preserve min/average/max CPU, RAM and GPU values; hover diagnostics show the range so short spikes are not hidden by averages.
- Raw XLSX resource export remains full-resolution for the selected retained range.

## List views and UI

- Removes **Hide failed URLs** from Opportunities and Hidden Leads toolbars while retaining URL-health data and backward compatibility for old `healthy=1` links.
- Every client-side list/sort view gets a search box if it does not already have one.
- List search uses rendered table-cell text only. Hidden `data-search` metadata and non-visible associated record fields cannot produce matches.
- Server-backed list searches were narrowed to their displayed list fields, preventing hidden descriptions/company research from matching unrelated rows (for example a search for `technical writing`).
- Adds consistent mild hover/active/focus behavior to text buttons. Candidate Profile **Defaults** is a normal action button rather than a selected-looking toggle; the same interaction rules apply to Auto-create Campaign Templates and other button variants.
- Outgoing Test Body aligns with Recipient/Subject input geometry and has a roughly 160px resizable default height.

## Address Book audit/provenance

- Stops generating routine `addressbook_promotion` AuditLog rows.
- Campaign/run/source provenance is stored on the Contact instead and campaign effectiveness reporting reads that provenance.
- Upgrade migration backfills available provenance from old promotion audit rows before deleting that audit noise.

## Upgrade

Standard ScoutBox upgrade procedure applies. Run database migrations before starting the new web/workers. The migration performs deterministic local data repair only and does not make billable AI calls.
