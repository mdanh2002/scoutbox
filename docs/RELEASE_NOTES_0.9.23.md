# ScoutBox 0.9.23

## AI & Discovery

- Discovery method and the active routing configuration now live in one responsive card rather than separate visual boxes.
- The Local Discovery routing explanation requested for removal is no longer displayed.
- Cloud Web `Auto-select all` is now `Auto-detect`.
- Cloud Web Auto-detect is metadata/documentation driven. It does not list models from the provider, make a live web-search capability probe, or require an API key merely to prepare defaults.
- `Test Selection` is the live validation step for the exact persisted stage routes.
- Documented Cloud defaults are stage-aware: routine Discovery work uses economical Primary/Failover pairs, while resume tailoring, application questions and import inference may use a stronger Primary. Primary and Failover remain on the same provider within each stage.
- The Request timeouts heading and redundant per-attempt explanation are hidden while the actual timeout configuration fields remain available.

## Chatbot

- Chatbot Auto-detect opens a runtime-choice popup when Local and/or Cloud AI are configured; it no longer silently forces Cloud.
- Local Chatbot Auto-detect respects the same conservative automatic hardware ceiling as Local Discovery, using the smaller detected system-RAM/discrete-GPU-VRAM limit. Manual model selection is still unrestricted.
- Cloud Chatbot Auto-detect uses a stronger documented Primary and a lower-cost same-provider Secondary. Live verification remains behind the explicit Test buttons.
- Legacy Chatbot input ceilings at or below the old 28k default are upgraded on Save to the current runtime default (48k Local / 32k Cloud); larger deliberate caps are preserved.
- Chatbot context preparation is now intent-aware and bounded. ScoutBox keeps the complete live workspace available to its classifier but initially injects only the identity/date information needed for the question.
- Latest/recent questions receive a small recency directory plus richer details for the requested records. Detail/follow-up questions search the complete loaded workspace first, then inject only matching rich records.
- This prevents simple requests such as “tell me about the latest 5 opportunities and leads” from failing merely because unrelated records make the overall workspace large.
- Prompt guidance tells the model to answer confidently from supplied evidence while distinguishing genuine uncertainty from fields intentionally not loaded for the current question.

## About ScoutBox / Redis

- Common data checks now has an icon, divider and its own bordered panel.
- Useful scripts & key files, Terminal & SQL examples, Common data checks and Redis usage share a consistent subsection heading treatment.
- Long Redis/Django shell examples are split across lines, and Redis command code wraps inside the card so horizontal command scrollbars are avoided.
- The Redis learning reference still explains queue depth, safe key inspection, Celery envelope extraction, task-result metadata, broker health and read-only learning commands.
- `./print_creds.sh` keeps its sensitive-output warning text but no longer has the yellow command highlight.

## Compatibility

No new database schema migration is required for 0.9.23. Migration `0074_v0922_cloud_web_stage_routes` remains included for upgrades that have not yet applied the 0.9.22 Cloud Web routing change.
