# ScoutBox 0.9.9 Release Notes

ScoutBox 0.9.9 fixes background AI jobs that could appear permanently queued while Address Book company enrichment waited behind Local AI Discovery.

## Background company research

- Queued CampaignRuns are no longer treated as active Local AI work. Only fresh `running` runs and short-lived `stopping` runs block company research.
- Waiting jobs record the blocking campaign, stage, retry count, wait start, latest wait activity and next retry time.
- AI Requests placeholders refresh their timestamp/message while a background job is waiting, so the list no longer looks frozen at the original enqueue time.
- Background company-research waiting is capped at 120 minutes by default (`SCOUTBOX_LOCAL_BACKGROUND_WAIT_MAX_MINUTES`, 15–480 minutes). On expiry the BackgroundJob is finalized as Failed with an explicit expired-wait reason rather than remaining queued forever.

## Campaign queue watchdog

- CampaignRuns that remain `queued` without ever reaching a worker are finalized after 30 minutes by default (`SCOUTBOX_CAMPAIGN_QUEUE_STALE_MINUTES`, 10–240 minutes).
- Campaign task startup uses compare-and-set updates, so a watchdog-finalized run cannot later be revived by a delayed Celery delivery.

No database migration is added in 0.9.9.
