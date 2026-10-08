# ScoutBox 0.10.51

Focused reliability release for the legacy release backfill waiter.

## Fixed

- Finalizes stale queued/running `0.10.41 upgrade backfill` jobs during migration so old startup repair rows cannot remain active forever.
- Updates startup seeding to complete stale/waiting legacy backfill jobs and save the completion marker instead of reusing an orphaned queued job.
- Changes the 0.10.41 release-repair task so Local Discovery activity causes a completed/skipped repair state, not an indefinite retry loop.
- Keeps the rest of the 0.10.50 codebase behavior unchanged.

## Upgrade

Replace the package and run the normal restart flow. Migration `0097_v01051_backfill_unstick` is included and requires no manual data entry.
