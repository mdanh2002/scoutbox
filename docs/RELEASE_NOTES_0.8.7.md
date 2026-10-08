# ScoutBox 0.8.7 release notes

ScoutBox 0.8.7 builds on the verified 0.8.6 package and focuses on configuration completeness, diagnostics, list-view consistency, IMAP usability and faster opportunity review. It does not add a database schema migration beyond `portal/0008_v086_ui_read_summary.py`.

## Navigation and configuration

- Renamed the left navigation group to **Quick View**, with Dashboard, Candidate Profile and Engagement Preferences together at the top.
- Renamed the left-menu **System Configuration** entry to **Configuration**.
- Restored the complete single Configuration bar: General, Search & Processing, Search Sources, Email, Tracking Links, AI & Discovery, ToughDev Stats, Users and Maintenance.
- Renamed the Configuration **Administrators** tab to **Users** without changing administrator-account behavior.
- Kept exactly one Configuration tab bar per configuration page.
- Moved Logout below the copyright block and removed the sidebar last-modified line; version/build date now appears as the last line of Dashboard Diagnostics.

## Mail and ToughDev integration

- IMAP Browser now keeps Inbox, Drafts and Sent visible even when a lightweight/internal IMAP server does not immediately return newly created folders from LIST.
- Improved spacing between Refresh Folders, folder selector, Populate Test Emails and message-count status.
- Internal Development mailbox still offers Populate Test Emails, producing representative Inbox, Drafts and Sent messages.
- ToughDev read-only SELECT testing is now queued asynchronously and polled without reloading the page, including clean failure reporting for invalid credentials.
- Tracking-link resolution now accepts same-host canonical redirects between http/https, www/non-www and `/blog/<slug>` / root article routes while still rejecting off-host redirects.
- DOCX hyperlink scanning uses the same normalized ToughDev host logic.

## AI, discovery and diagnostics

- Simplified the Discovery mode control and retained a single dropdown.
- Added **Automatic Routing** and **Best Local Defaults** pipeline presets; the local preset assigns suitable installed Ollama models only.
- Ollama provider diagnostics show runtime status first and installed model chips on a separate line.
- Test Discovery now records stage-by-stage query/provider/output/error information and offers **View details**, including zero-result runs.
- Opportunity AI summaries are queued during first discovery instead of being triggered implicitly when a user opens an opportunity.
- Search Sources show provider health beside search-engine names: green when ready/healthy, yellow for elevated errors and red when disabled/unconfigured.
- Dashboard shows aggregate search-provider health and inserts an elevated-error warning when provider failures are high; the 24-hour error metric receives stronger visual emphasis at elevated counts.

## Opportunities and post age

- Opportunity list Last scanned metadata is shown at the bottom of the list rather than above the toolbar.
- Fit uses a five-bar signal-style icon with red/grey/yellow/green progression.
- Source and status icons no longer use identical circular chrome.
- Post Age uses distinct semantic icons for new, medium, old, unknown and evergreen-ready states.
- Opportunity detail shows raw fit score alongside the same signal icon and provides a labelled status control with a Save action at top right.
- Post-age evidence has an information control that exposes the deduction sources.
- Freshness analysis now also reads publication-age evidence from the target document itself: metadata, JSON-LD, HTML time elements, HTTP metadata, visible date phrases and cautious relative-age text, in addition to existing portal/source/archive evidence.
- Existing Search URL / Target URL deduplication is retained when both point to the same location.

## Dashboard, statistics and list layout

- Ask ScoutBox launch control now sits at the top right immediately before the search-status dot; conversation history remains persisted across page navigation.
- Discovery Activity puts Last updated immediately to the left of Today/Week/Month/Year.
- Recent Activity is a direct grid without the previous collapsible technical-activity wrapper.
- Statistics now displays Opportunities by Discovery Source as a full-width table.
- Opportunity Status, Search Provider Summary and Discovery Source Share are visualized as charts together at the bottom of Statistics rather than as scattered tag rows.
- Resource Usage date-range and Today/Week/Month/All controls are kept on one clean row on normal desktop widths.
- Email History no longer repeats Incoming/Outgoing/Draft headings inside the selected tab.

## Maintenance

- Added **Clear Logs & Telemetry**, protected by `CLEAR LOGS` confirmation. It clears accumulated audit records, completed/failed task history, usage metrics, search-provider statistics, resource samples, diagnostics and performance runs.
- Clear Logs & Telemetry deliberately preserves candidate profile/CVs, opportunities, applications, email credentials and configuration.
- Added concise maintenance caution text below the destructive-action buttons.

## Market Studies and existing 0.8.6 workflows

- Fixed the Market Studies `Areas` template alias used by older rows, preventing the reported `/cold-contact/` rendering failure and continuing to strip `Relevant work:` / `Relevant technical work:` prefixes.
- Market Studies and Campaigns retain Select All, row selection, Delete Selected/Delete All and the compact 0.8.6 toolbars.
- Tracking Links, Blacklist, Applied Roles, Application Drafts and Address Book retain their 0.8.6 bulk-management and XLSX-export behavior.
