# ScoutBox 0.8.52

0.8.52 is a focused corrective release on top of 0.8.51.

## Changes

- Fix Local AI readiness on Apple Silicon: a fresh host telemetry identity of macOS/Darwin on arm64 is valid local accelerator evidence even when GPU utilization and separate VRAM counters are unavailable.
- Keep Linux/NVIDIA detection unchanged and continue showing discrete VRAM only where it exists.
- Make Test Selection/model-test accelerator evidence use the same host-identity-aware logic.
- Replace the Host Disk Used hover breakdown with a compact top-right info icon and a click-open disk usage detail dialog.
- Refresh the disk detail dialog contents with live Resource Usage updates.
- No database migration is required.
