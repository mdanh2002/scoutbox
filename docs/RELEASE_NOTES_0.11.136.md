# ScoutBox 0.11.136 Release Notes

## SearchAPI preflight and telemetry

- SearchAPI services now stop before network dispatch when no API key is configured.
- Missing credentials no longer create Search Activity rows, AI Request rows, provider request counts, errors, or SearchAPI quota usage.
- Manual Test Search returns a configuration message without recording a fake request when no key exists.
- Migration 0208 removes false no-key SearchAPI telemetry created by 0.11.135 and repairs the corresponding daily provider counters.

## SearchAPI dialog

- Removed the redundant “SearchAPI API” text after the configuration status badge.
- Moved Save to a new left-aligned row beneath Google Local / Employer Discovery and the other service controls.
- Made the full SearchAPI modal vertically scrollable while keeping horizontal overflow suppressed.
- Preserved the single-line desktop Test Search layout and responsive mobile wrapping.

## Schedule / Limits

- SearchAPI daily limit remains the final limit control, but the separate “SearchAPI Limit” heading and shared-pool explanatory paragraph were removed.
- Quota speedometer state colors remain unchanged on hover/focus.

## Preserved functionality

Unified SearchAPI service selection, SearchAPI ChatGPT Cloud Runtime logging, shared daily quota accounting, Google Jobs/Web/Forums/News/AI Mode/Local support, worldwide coverage, community hiring signals, multilingual discovery and prior re-evaluation safeguards are retained.
