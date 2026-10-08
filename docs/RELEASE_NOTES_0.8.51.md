# ScoutBox 0.8.51

0.8.51 is a focused readiness and interface corrective release on top of 0.8.50.

## AI readiness

- Treats Ollama `/api/ps` as optional telemetry rather than a prerequisite for a healthy local runtime.
- Records accelerator evidence independently from Ollama running-model telemetry and host GPU telemetry during model tests.
- Recent successful accelerator-backed model validation can prevent false Local GPU unavailable warnings during temporary telemetry gaps.
- Local GPU and validated Cloud AI remain independent valid readiness routes.
- When AI is genuinely unavailable, scheduled-search/campaign messaging is suppressed until a usable route returns.
- Dashboard and the top-right status expose Configure and Show Logs actions; the readiness log shows the evidence used for each provider decision.

## Interface cleanup

- Consolidates the Discovery Method guidance into one concise line directly below the selector.
- Ollama test answers render on a separate line beneath the test status.
- Shortens destructive-maintenance and other configuration guidance.
- Moves Save profile beside the Candidate Profile heading.
- Tightens AI Requests filters so request count/export remain on the toolbar at normal desktop widths.
- Moves a shorter Recycle Bin retention/suppression note below pagination.

## Resource Usage

- Host Disk Used now exposes a hover breakdown for PostgreSQL, uploads/media, Ollama models, ScoutBox application/runtime files, and remaining host/Docker/system storage.
- Disk breakdown refresh is cached briefly to avoid repeatedly walking filesystem trees during live telemetry polling.

No new database migration is required.
