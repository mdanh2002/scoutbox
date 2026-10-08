# ScoutBox 0.10.5

## Live activity awareness in Ask ScoutBox

- Added a live `current_activity` snapshot backed by `CampaignRun` and `BackgroundJob`, the persisted work-state records already used by ScoutBox operational UI.
- The snapshot reports running/queued state, progress, campaign or job identity, stage/message, start/heartbeat information, wait metadata, and stall information where available.
- `BackgroundJob(kind=chatbot)` rows are deliberately excluded so an activity question does not report its own Ask ScoutBox request as the work being performed.
- The chatbot classifier now recognizes direct activity/status questions such as `What is ScoutBox doing at the moment?`, `What is running?`, `current activity`, and active/queued/background-task queries.
- Direct activity-overview questions are rendered deterministically from live persisted state. This prevents small local models from replacing an empty or specific activity list with generic claims such as `reviewing and analyzing the complete loaded workspace`.
- More diagnostic questions about active work still route through the configured Chatbot model with `current_activity` included as authoritative context.
- Idle and paused states are explicit. A failed context load is reported as unavailable rather than incorrectly reported as idle.

## Existing chatbot correctness protections

- Address Book recommendation answers still enforce stored email/contact methods and company background.
- Address Book totals, country/location queries, missing-contact suppression, public URL/email protection, and safe record-linking remain intact.

## Release numbering

Routine future releases increment the patch component: **0.10.6, 0.10.7, ...**. The 0.10.x line is retained unless a deliberately major release is designated.
