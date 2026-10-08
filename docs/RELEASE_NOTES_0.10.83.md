# ScoutBox 0.10.83

- Restores the default Local Discovery campaign concurrency to four in-flight campaigns, matching the older high-throughput behavior.
- Updates the discovery worker Compose concurrency to four so the scheduler cap and worker capacity agree.
- Keeps Forum discovery intentionally idle-only and low frequency. Forum inactivity for an hour or more is expected when primary campaigns or background work are active, and it prevents Forums from stealing throughput from search engines/direct discovery.
- Retains v0.10.82 query sanitization, campaign status cleanup, Email History toolbar cleanup, and all prior Forum safeguards.
