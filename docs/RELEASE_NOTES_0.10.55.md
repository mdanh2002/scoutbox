# ScoutBox 0.10.55

Focused reliability release.

- Campaign worker watchdog no longer fails running Local Discovery jobs solely because Celery inspect temporarily omits the task. Database heartbeat/stall timeout is now the authoritative finalizer.
- Campaign stall timeout is more conservative by default so slow providers/local models do not produce false `Campaign worker task is no longer active` failures.
- Default discovery worker concurrency is reduced to one campaign worker lane to avoid local model contention.
- Address Book Fit persistence no longer tries to save a non-existent `updated_at` field on `Contact`.
- Address Book contacts without direct AI Fit now receive an explicit inherited or deterministic low-confidence fallback when enough evidence exists, instead of showing `?` forever.
- Migration `0100_v01055_campaign_worker_contact_fit.py` backfills existing Address Book Fit fallback data.

Release numbering: Routine future releases increment the patch component.
