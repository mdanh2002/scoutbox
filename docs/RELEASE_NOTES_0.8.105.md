# ScoutBox 0.8.105

## Compensation cleanup

- Opportunity salary rows are now hidden when ScoutBox has no credible numeric compensation. `Salary not found` no longer occupies list-view space.
- Salary display requires a numeric amount. Job-board boilerplate such as `Sign in and add your salary to see matches`, `Competitive salary`, qualitative `high`/`average` labels, and bonus-only marketing text are ignored.
- Retained job-description/source compensation remains authoritative. Job-post salary links are not repeated in the Summary cell because the role URL is already visible in the first column; a distinct external salary-research source can still be linked.
- Numeric source-page estimates/benchmarks are retained even when they omit a currency, but ScoutBox will not compare those against Engagement Preferences until the currency is known.
- Migration `0065_v08105_salary_company_repair` reparses historical salary evidence locally and removes stale qualitative/noisy salary values. It makes no network or AI calls.

## Ask ScoutBox

- The Chatbot header now states whether internet search is on, off, or unavailable for the selected provider.
- Assistant responses support lightweight Markdown: headings, bullets, bold, italic, Markdown links, and bare `http://` / `https://` URLs. Inline backticks are rendered as italic text for the current UI.
- The persistent queued Chatbot behavior from 0.8.104 remains: leaving the panel/page does not cancel a server-accepted answer, and unread completed answers are reflected by the Ask ScoutBox badge.

## Company Info repair

- Fixed the Cloud Web Hidden Lead path that previously discarded company-size/founding context before persisting the lead. Future Cloud Hidden Leads now retain the Company Info returned by the discovery pass itself.
- Cloud-discovered Address Book contacts now inherit the same company intelligence, summary and company location context instead of losing it during contact qualification.
- Local Hidden Leads receive a deterministic retained-evidence Company Info baseline without Cloud calls.
- Address Book creation/import reuses Company Info from the originating Opportunity/Hidden Lead/company-domain cache and queues company research only when age/size remains missing.
- A one-time `0.8.105 Company Info backfill` background task repairs active Hidden Leads, Opportunities and Address Book records. In Local Discovery mode it waits/pauses while campaigns are active so it does not contend with the local GPU/search pipeline. The release is marked backfilled only after the task finishes, so an interrupted worker can retry on the next startup.
- The list view can show a collected company profile while age/size research is pending instead of presenting every partially enriched company as completely unknown.

## Configuration polish

- Portal Root URL Auto-detect now matches the height of the URL input.
- Resend API requests identify this release as `ScoutBox/0.8.105`.

## Upgrade

Keep the existing `.env` and Docker volumes. Apply the upgrade overlay or replace the application tree with the full package, then restart with the normal ScoutBox upgrade/restart procedure. No data-reset operation is required.
