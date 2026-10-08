# ScoutBox 0.11.143 — Restart-aware Campaign Recovery

- Fix CampaignRun rows remaining `running` for up to 20 minutes after `restart_scout_box.sh` stops the worker containers during an upgrade.
- Detect the preceding graceful `service_stopped` lifecycle boundary during bootstrap instead of treating the absence of workers as an ambiguous Celery-inspection failure.
- Immediately finalize running campaign rows whose heartbeat belongs to the stopped worker generation.
- Reconstruct any Opportunities / Hidden Leads already persisted by the interrupted run before finalization.
- Queue an equivalent replacement campaign run for the new worker generation and preserve the original rotation/window attempt.
- Mark the interrupted row coverage-exempt so restart recovery cannot consume two campaign coverage slots.
- Clear stale `scoutbox:local-ai:lane:*` mutexes when a full-stack restart is proven, preventing a dead Ollama lane owner from delaying new campaign work.
- Immediately finalize running Background Jobs that are proven to belong to the stopped stack; queued jobs remain untouched because broker state survives the normal upgrade process.
- Reuse the existing automatic company-research recovery path for Background Jobs interrupted by restart.
- Keep the conservative ownership/heartbeat watchdog behavior for ordinary runtime conditions and web-only restarts with live workers.
- Preserve all 0.11.142 Page Title wrapping and 0.11.141 source-coverage / YC fixes.
