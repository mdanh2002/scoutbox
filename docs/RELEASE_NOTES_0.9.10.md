# ScoutBox 0.9.10 Release Notes

ScoutBox 0.9.10 fixes the Celery worker starvation that could leave Address Book `company_enrichment` AI Request placeholders queued indefinitely while long Local Discovery campaigns occupied both worker slots.

## Queue isolation

- `run_campaign_job` is routed to a dedicated `discovery` queue.
- The existing historical `celery` queue is retained as the background/default queue so queued jobs published by earlier releases remain consumable after upgrade.
- Docker Compose now runs a dedicated `discovery_worker` in addition to the normal background `worker`.
- Both workers use `--prefetch-multiplier=1`; Celery's global prefetch multiplier is also set to 1.
- Hidden Leads scans, Address Book company research, summaries, mailbox work, scheduler ticks and other non-campaign tasks remain on the background queue and no longer wait for a campaign to release a Celery slot.

## Stale task reconciliation

- The scheduler compares BackgroundJob and CampaignRun task IDs with Celery active/reserved/scheduled ownership.
- Dead CampaignRun worker ownership is detected quickly after restart, so an old fresh-looking heartbeat cannot keep Address Book enrichment waiting for a campaign that no longer exists.
- Long-running rows that are no longer owned by any worker are finalized as interrupted instead of remaining permanent hourglasses.
- Very old queued rows that have disappeared from Celery are finalized as queue-expired; scheduled retries are preserved.
- Finalization refreshes the corresponding AI Requests placeholder, so stale queued/running icons do not remain after the watchdog closes a job.
- Startup runs the same reconciliation conservatively before normal workers begin accepting new work.

## Diagnostics

System Diagnostics now reports whether both the `celery` background queue and `discovery` queue have active consumers.

No database migration is added in 0.9.10.
