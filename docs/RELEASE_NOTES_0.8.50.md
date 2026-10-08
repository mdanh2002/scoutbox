# ScoutBox 0.8.50

0.8.50 is a focused UI/readiness corrective release on top of 0.8.49.

## AI readiness

- Successful local Test Selection now records direct Ollama VRAM/GPU evidence while the tested model is loaded.
- Readiness accepts that validated accelerator evidence when host telemetry is temporarily unavailable inside Docker.
- Local, Cloud, or mixed Local+Cloud configurations remain valid independently; a working route prevents the global unavailable warning.
- Global unavailable wording is provider-neutral (`No usable AI route.`) instead of incorrectly blaming the Local GPU when Cloud AI may also be configured.

## UI copy

- Shortens AI & Discovery readiness, Discovery Method, Cloud priority, Chatbot, and Test Discovery hints.
- Shortens Search Sources Preferred Sources, Schedule / Limits, Local limits, Cloud limits, and higher-cost warning text.
- The Preferred Sources hint retains its link to the Sources panel.
- Dashboard and top-right unavailable messages are shorter.

## Tracking links

- Widens the Clicks column and prevents `N (N human)` from wrapping for normal three-digit counts.

No new database migration is required.
