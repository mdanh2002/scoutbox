# ScoutBox 0.10.118

Hotfix release for Focus taxonomy rebuild scheduling.

- Forces a version-gated Focus taxonomy quality rebuild after upgrade, even when old Focus values are nonblank.
- The rebuild is queued after web health as a visible Dashboard Activity job: `Refresh Focus taxonomy quality for 0.10.118`.
- Startup migrations remain database-only and fast; no LLM, page fetching, or bulk classification occurs before health.
- Same-release failed rebuilds are throttled for 24 hours, but earlier-release attempt timestamps no longer suppress the first 0.10.118 rebuild.
