# ScoutBox 0.10.57

Focused Local Discovery throughput/stability release.

- Restores automatic Local Discovery campaign concurrency to 2 instead of serializing all discovery work through a single campaign lane.
- Keeps the discovery worker concurrency at 2 so one long campaign does not block all other due campaigns.
- Adds a Redis-backed local AI generation lane semaphore for campaign Ollama calls. Campaigns may search, fetch, dedupe and save concurrently, while accelerator-heavy local model generation is limited by `SCOUTBOX_LOCAL_AI_GENERATION_LANES`.
- Adds visible campaign heartbeat/status updates while a run waits for a local AI lane, so Dashboard status shows contention instead of appearing frozen.
- Adds process-safe provider pacing for public search providers to reduce parallel 403/429 cascades without reducing campaign concurrency globally.
- Retains the 0.10.55 heartbeat-authoritative watchdog and partial-result reconstruction behavior.
- No database migration is required.

Release numbering: Routine future releases increment the patch component.
