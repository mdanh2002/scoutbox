# ScoutBox 0.10.6

## Human-readable live activity in Ask ScoutBox

- Reworked the deterministic current-activity response so it explains the work ScoutBox is performing rather than leading with raw counts such as `2 running`.
- Running Campaign Runs are explicitly treated as opportunity/lead discovery activity.
- When a Campaign Run is in a search stage, ScoutBox says it is **actively searching for new opportunities/leads** and translates persisted stages such as `Searching Yandex: <query>` into readable per-campaign descriptions.
- Search query display removes harmless persisted Markdown escapes such as `site\:example.com` -> `site:example.com`.
- Campaign activity rows now carry `work_type=opportunity_lead_discovery` and a `current_action` of `searching`, `processing`, or `queued`. These semantics are also available to model-routed diagnostic activity questions.
- Background Jobs receive task-specific descriptions (company research, Hidden Lead scanning, Opportunity filtering, application preparation, mailbox scanning, etc.) rather than generic `Running` labels.
- Queue counts, progress, waiting reasons, stall information, paused state, and explicit idle state remain available.

## Regression coverage

- Added the exact two-campaign/Yandex case that previously rendered as `ScoutBox currently has 2 running`.
- The regression requires the response to say ScoutBox is actively searching, preserve both campaign names, display their actual Yandex queries, and include 37% progress.
- Existing Address Book, location-query, URL/email-linking, summary-cleanup, and activity-state regressions remain packaged in the single current verifier.

## Database / upgrade

No database migration is required for 0.10.6. Existing `CampaignRun` and `BackgroundJob` rows remain the source of truth.

## Release numbering

Routine future releases increment the patch component: **0.10.7, 0.10.8, ...**. The 0.10.x line is retained unless a deliberately major release is designated.
