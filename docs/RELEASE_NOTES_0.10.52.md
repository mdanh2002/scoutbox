# ScoutBox 0.10.52

Focused Local Discovery reliability repair.

- Fixed a campaign-planning crash where a settings dict/snapshot could be treated as a `PortalSettings` model object, producing `'dict' object has no attribute 'scraper_interval_minutes'` before any query was built.
- Made the campaign worker-ownership watchdog conservative: a recent heartbeat prevents false `Campaign worker task is no longer active` failures caused by transient Celery inspect gaps.
- Added partial-result reconstruction for interrupted/stalled campaign runs based on persisted `campaign_run_id` provenance.
- Reduced default automatic Local Discovery concurrency to one campaign at a time unless overridden by `SCOUTBOX_DISCOVERY_AUTO_INFLIGHT`.
