# ScoutBox 0.10.81 release notes

## Local campaign crash and scheduler starvation

The one-hour diagnostic captured 61 failed campaign runs with the identical runtime error `name 'time' is not defined`. 0.10.80 added monotonic wall-clock budgets to Local AI search-engine execution but `portal/services/discovery.py` did not import Python's `time` module. A Local campaign therefore reached the new timer and failed before any search-provider work could complete.

A second scheduler bug amplified that failure. Normal runs historically omitted `forum_only=False` and `deferred_local_ai=False` from the CampaignRun JSON criteria. Scheduler accounting used negated JSON-key lookups to exclude Forum/deferred rows. On database backends where a missing JSON key does not satisfy that negated lookup, ordinary failed/completed runs could disappear from attempt accounting. The scheduler then treated the same campaign as having made no attempt and queued it again on the next one-minute tick. Because campaign ordering is stable, that retry loop could also starve later due campaigns, producing the Dashboard symptom “Next campaign (...) is due now” indefinitely.

0.10.81 imports the monotonic clock dependency, writes the scheduler flags explicitly for every new run, repairs historical criteria through migration `0109_v01081_campaign_run_flags`, and replaces unsafe normal-run exclusion logic with positive primary-run predicates that also recognize legacy rows. Deferred Local-AI attempts now obey the normal intra-window backoff, while two recent failed primary attempts trip a per-window circuit breaker. A deterministic failure can therefore no longer generate one CampaignRun per scheduler tick.

## Dashboard and Cloud/Forum accounting

The next-run estimator now ignores Forum-only passes when calculating primary Local or Cloud scheduling. Cloud daily automatic-run accounting likewise treats Forum passes as supplementary and does not let them consume the primary Cloud campaign quota. Forum preemption checks recognize both explicit current flags and pre-upgrade rows with missing flags.

The Forum deep-idle scheduling, one-source/25-second Forum bounds, dedicated Forum worker, degraded search-engine recovery cooldown and adaptive source balancing from 0.10.80 are otherwise unchanged.

## Upgrade

Migration `0109_v01081_campaign_run_flags` updates only CampaignRun JSON metadata. It does not delete opportunities, leads, contacts, applications or campaign history. Existing failed 0.10.80 runs remain visible for diagnostics, but after migration they are correctly counted so they cannot trigger the old retry storm. Recreate/restart the normal ScoutBox stack so web, scheduler and workers all run the 0.10.81 code.
