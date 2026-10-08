# ScoutBox 0.8.35 Release Notes

Released on 2026-08-20 23:04:00.

## Recycle Bin

- Recycle Bin is now a standalone System page rather than a Configuration tab.
- The System menu shows a non-bold numeric Recycle Bin badge only when recycled items exist.
- Campaigns, Opportunities, Hidden Leads, Applications and Outreach records are supported.
- The list adds the original Item Date alongside Date Deleted, Item Title and Item Type.
- Search, rows-per-page, pagination and the sticky list toolbar are available.
- Per-row Restore was removed. The toolbar now provides Select All, Restore Selected with confirmation, Delete Selected with confirmation, and Empty Recycle Bin.
- Restored campaigns remain paused. Recycled Opportunities and Hidden Leads continue to suppress rediscovery until permanently removed.

## Campaigns and first-run scheduling

- Campaign list adds sortable Last Run Duration in minutes using the latest finished campaign run, including failed/stopped completed runs where timing is available.
- Empty duration cells stay blank when no completed run exists.
- Pause/Resume uses compact icon controls instead of text buttons.
- The automatic scheduler no longer starts discovery on a fresh installation with no active Resume/CV. Once a Resume/CV exists, normal scheduling resumes; uploading a CV does not force an immediate special run.

## AI & Discovery

- “Retailor” terminology is replaced with “Personalize Email”.
- Application/outreach email prompts use CV evidence, Candidate Profile, role evidence and collected Company Profile evidence. When company evidence exists, the prompt asks for 1–2 concrete company-specific lines tied to evidenced candidate experience; it explicitly forbids invented company claims and generic praise.
- The separate Test Discovery tab is removed. Test Discovery is a button on Discovery and opens the former diagnostic content in a popup.
- Test Discovery now resolves configured enabled search providers even when temporary provider budget/backoff would otherwise make the diagnostic incorrectly report that no provider is enabled. It remains non-persistent.
- A Test Model button is placed after Optimize for Cloud and before Test Discovery.
- Test Model validates each pipeline stage’s resolved primary model and configured fallback using the stage’s production request path/token parameters, with small prompts and hard timeouts. Cloud Web URL discovery validates the cloud web-search-capable route.
- Pipeline stage names now have large borderless status symbols: gray `?` before validation, green check for compatible routes, and yellow `!` for failures/incompatibilities. Tooltips show the resolved provider/model and result. Saved routing changes invalidate stale test results; unsaved control changes reset the visible stage indicator immediately.
- The “Pipeline routing” heading text is hidden/removed.

## Lists, notifications and logs

- Hidden Leads default to newest Date Added first; Opportunities remain newest first; Applications & Outreach default A–Z by Role/Company.
- Country is removed as a standalone column from Opportunities, Hidden Leads and Applications & Outreach. It appears as a small muted final line under Role/Company (or Company for Hidden Leads), with flag when available.
- Contact/URL is placed immediately after Role/Company in Opportunities and Applications & Outreach.
- The top-right recent Opportunities/Leads popover refreshes its rows immediately together with unread counts after read/unread state changes.
- Search Activity Date is widened to show seconds and Query is constrained with ellipsis to avoid unnecessary horizontal scrolling. Existing server-side sorting remains available for all Search Activity columns.
- Resource Usage / provider performance leaves Last Error blank when no error exists.
- Optional empty cells in other affected tables no longer use decorative dash placeholders where the value is simply absent.
- Audit Trail renames the visible Object heading to Data and Action is sortable.

## Dashboard and authentication UI

- Dashboard Diagnostics can generate and store a live diagnostics snapshot when no completed snapshot is available, instead of showing the broken “No diagnostics snapshot is available” state. Individual component failures remain visible as rows rather than blanking the panel.
- Forgot Password is removed from the login experience and password-reset routes are no longer exposed. No Change Password UI is added.
- Version/build labels now say “Released on …” rather than “Last modified …”.

## Preserved 0.8.34 reliability fixes

- Hidden Lead Recycle Bin lifecycle and rediscovery suppression.
- Google public-search browser-fingerprint/pacing behavior and concise block/error reporting.
- Company Info baseline/research refresh behavior.
- Aggregate job-list pages (including Indeed collection/search pages) are rejected as single opportunities.
- Sticky standalone list toolbars and blank AI-request attachment cells.
