# ScoutBox 0.8.109 Release Notes

Released 26 August 2026.

ScoutBox 0.8.109 is a UI, diagnostics and reliability refinement release built on the telemetry and discovery changes in 0.8.108. It does not add a new database migration; migration `0068_v08108_usage_visibility_salary_cleanup.py` remains the latest required migration.

## Resource Usage

- Large counters now use compact human-readable notation only at one million and above. Examples: `15,200,000` displays as `15.2M` and `2,500,000,000` as `2.5B`.
- Values below one million retain their full numeric value rather than being shortened to thousands.
- The compact formatting is applied to live-refreshed totals as well as server-rendered Resource Usage and Cloud Usage figures.
- Removed the “Recorded for selected period” label from Cloud Usage because it duplicated the period selector and could be mistaken for a limit/status message.
- The CPU/RAM/Tokens chart behavior is unchanged.

## Ask ScoutBox links

- Deterministic workspace answers for matching Opportunities and Hidden Leads now render ScoutBox detail links for each result.
- The complete-dataset and fail-closed behavior introduced in 0.8.108 remains intact.

## AI Request payload viewer

- Input and Output sections now include a `View raw` checkbox.
- Valid JSON defaults to the interactive tree viewer; Expand/Collapse controls are shown only in that mode.
- Raw mode disables the JSON tree while preserving lexical syntax highlighting.
- Plain/non-JSON payloads show a highlighted raw representation and do not show misleading Expand/Collapse controls.
- Copy-to-clipboard stays available in the section header regardless of display mode.

## About ScoutBox

- Corrected `1 entries` to `1 entry` while retaining plural wording for other values.
- Added a divider below the Troubleshooting Tips heading and increased the hierarchy of troubleshooting/architecture section headings.
- Added a full-width `Useful scripts & key files` reference below status/log/recovery guidance, covering common administrative scripts, `.env`, `.env.example`, Docker Compose and persistent media.
- Existing 0.8.108 architecture counts for Opportunities, Hidden Leads, Contacts, Applications/Outreach, configured cloud providers, local Ollama models and persistent storage consumption remain included.

## Search Activity

- The `Size` heading for downloaded payload size is now centered to match its compact numeric column.

## IMAP Browser

- Opening a message now displays the modal immediately with a loading state while the message is fetched.
- HTML email is rendered in a sandboxed iframe, preventing email CSS/background styles from leaking into the ScoutBox dialog/theme.
- Header metadata labels now read `From:`, `To:`, `Date:` and `Folder:`.
- Delete Draft is hidden/disabled outside the configured Drafts folder. Server-side delete authorization continues to compare the selected folder against the configured Drafts folder case-insensitively.
- Load failures stay visible inside the already-open message dialog rather than leaving the user waiting for a modal that never appears.

## Compatibility

All changes are compatible with existing 0.8.108 data and Docker volumes. Existing installations should keep `.env` and volumes, replace application files, and run `./restart_scout_box.sh`.
