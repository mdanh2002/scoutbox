# ScoutBox 0.11.145 — Resource Usage Panel Cleanup

## Changed

- Removed the extra Resource Usage status strip showing Hardware archive, Hardware coverage, GPU coverage, and GPU state.
- Removed the strip's dedicated live DOM updater and CSS.
- Kept the telemetry-health calculations/API data available internally for diagnostics and future use.

## Retained

- 0.11.144 GPU freshness/state persistence and bounded stale carry-forward.
- ResourceHourly archive and long-range hardware-history fallback.
- Telemetry sampler degradation logging, upgrade smoke checks, and diagnostic export coverage.
- 0.11.143 restart recovery, 0.11.142 Facebook Page title wrapping, and 0.11.141 source-coverage / YC fixes.

## Data integrity

No telemetry rows are deleted or rewritten by this release. Migration 0217 records the version upgrade only.
