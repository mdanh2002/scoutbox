# ScoutBox 0.10.75

0.10.75 prevents Local AI discovery runs from piling up behind a single Ollama generation lane.

Changes:
- Automatic Local AI discovery is now capped by the configured local generation lane count.
- Local AI lane waits are bounded to a short retry window instead of waiting for many minutes.
- When the lane remains busy, the campaign run is deferred cleanly and retried by the scheduler later.
- Query-planning alias enrichment skips optional local-model work when the local AI lane is busy.
- Upgrade migration releases already-running Local AI contention rows so the new policy can take over.
