# ScoutBox 0.9.5 Release Notes

## Host telemetry resilience

The host telemetry heartbeat no longer waits for slow GPU commands. GPU probing runs in a background sampler, while CPU, RAM and disk snapshots continue to publish independently. A single failed GPU probe keeps the last successful utilization reading for a short grace period; genuinely unavailable GPU telemetry still becomes null instead of being fabricated.

On macOS, `start_host_telemetry.sh` now installs and refreshes a per-user LaunchAgent with `RunAtLoad` and `KeepAlive`, so the host bridge restarts after process exits and is more resilient around sleep/wake. Environments where launchd cannot be used automatically fall back to the existing `nohup` process.

## Resource Usage presentation

The current status area is a single responsive line containing CPU, RAM, GPU utilization, Requests, Local Tokens, Cloud Tokens, Disk and GPU Model. The separate Disk/GPU metadata row is removed. Requests are drawn with a solid line; genuine null GPU samples still remain gaps.

## Recycle Bin and pagination

Recycle Bin bulk actions now use distinct icon-only controls for Blacklist, Restore, Delete and Empty, with titles and ARIA labels. The currently selected page in shared list pagers no longer shows a `not-allowed` cursor on hover.

No database migration is added in 0.9.5.
