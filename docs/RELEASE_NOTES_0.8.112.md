# ScoutBox 0.8.112 Release Notes

Released 26 August 2026.

ScoutBox 0.8.112 is a focused UI/reliability release for Chatbot configuration, AI Request payload viewing, the Incoming IMAP Browser, and Hidden Leads list layout. It does not change Cloud Web Discovery or Local GPU discovery logic.

## Chatbot configuration layout

- Primary and Secondary failover routes are displayed one below the other instead of in a two-column grid.
- Route semantics are unchanged: the Secondary route remains Chatbot-only and is invoked only when the Primary route fails or cannot fit the complete workspace context.
- Existing Primary/Secondary tests and Auto-select behavior are unchanged.

## AI Request JSON viewer

- JSON validation now normalizes recognized provider/Markdown wrappers before parsing.
- Supported wrappers include normal fenced JSON (` ```json ... ``` `), fences with whitespace, a loose `json` line label, and shortened closing backtick sequences sometimes returned by providers.
- Wrapper removal happens before JSON validation and tree rendering.
- Plain text that merely contains a JSON object is not promoted to a JSON payload; `View raw` stays completely hidden in that case.
- Valid JSON continues to offer tree mode, Expand/Collapse, and syntax-highlighted raw mode.
- Non-JSON text keeps lexical highlighting so JSON-like fragments are easier to scan, while Copy remains available for all payloads.

## Incoming IMAP Browser

- The old Refresh Folders text button is replaced by a refresh icon beside the IMAP Browser heading.
- Detect folders remains available next to the refresh control.
- Browse folder is now a fourth aligned folder row beneath Inbox, Drafts, and Sent.
- The persistent `N folder(s)` status text is removed.
- Test generation is shown as `Generate test emails:` with a compact `Generate` button aligned to the right of the field area.
- Refresh/detect and test-message generation are queued as background jobs. The page polls job status and updates the controls/table without a page navigation or reload.
- Refresh and Generate controls disable while an operation is active; refresh shows a spinning icon and Generate changes to `Generating…`.
- Existing IMAP test-message behavior is unchanged: one timestamped message is appended to each configured Inbox, Drafts, and Sent folder without sending external mail.

## Hidden Leads

- Fit now appears immediately before Added in the list view.

## Database / compatibility

No new migration is required. Existing 0.8.111 installations can retain `.env`, PostgreSQL/Redis/media volumes, and all records. Replace application files and run `./restart_scout_box.sh`.
