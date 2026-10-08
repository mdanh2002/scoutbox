# ScoutBox 0.11.27

## Fixed

- Hidden Lead existing-lead minibrowser reassessment now uses a durable single-owner execution lease so delayed or duplicate Celery deliveries cannot overwrite newer progress.
- Reassessment progress is saved monotonically from completed lead IDs and per-lead reassessment state; after a restart it resumes from the committed cursor instead of starting from the beginning.
- Queued/running reassessment jobs that lose worker ownership are redispatched quickly against the same BackgroundJob/pass instead of waiting for the generic queue watchdog timeout.
- The current lead shown in the reassessment banner is cleared after each item completes, preventing stale company/current-AI timers from lingering.
- Skip Current now re-dispatches through the same leased reassessment path and cannot create a competing worker.
- Campaign, Campaign Template, and Address Book list-view Add buttons now use the same plus glyph, dimensions, colors, and hover/active treatment.

## Notes

No database schema migration is required; the fix stores lease and cursor metadata in the existing durable reassessment pass JSON and BackgroundJob result JSON.
