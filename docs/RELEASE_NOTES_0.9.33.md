# ScoutBox 0.9.33

## Cloud provider rate-limit recovery

A Cloud Web campaign previously moved to 15% (`Cloud research`) and then failed immediately when the configured Cloud provider returned HTTP 429. Primary and failover models were attempted back-to-back, which is ineffective when the quota is shared by the provider/project.

0.9.33 adds campaign-only bounded backoff. ScoutBox reads `Retry-After` and Gemini `retryDelay` hints when available. If no usable hint exists, it uses short bounded waits. The total automatic wait for one logical Cloud request is capped, and the configured Primary/Failover relationship is preserved.

While waiting, the persisted CampaignRun message explicitly reports the provider cooldown and retry countdown. This keeps the 15% stage informative rather than appearing stuck.

If the provider remains rate-limited after backoff and failover, the run is stopped with `cloud_provider_rate_limited`, a retry timestamp and the provider/model details. This is treated as an external availability condition rather than a discovery-quality failure.

## Scheduler protection

After recent campaign HTTP 429s, automatic Cloud scheduling pauses briefly at provider level. This prevents the once-per-minute scheduler from immediately sending other campaigns into the same exhausted provider quota. Manual runs remain available and use the same bounded request-level backoff.

## Correct next-run calculation

The previous Dashboard estimator mirrored only the generic coverage window. In Cloud Web mode it could therefore display a past time such as 10:00 even when the actual scheduler was waiting on the configured Cloud minimum interval.

The estimator now includes:

- Cloud minimum interval per campaign;
- automatic Cloud runs-per-campaign daily limit;
- recent provider rate-limit cooldown;
- current coverage window and spacing;
- the scheduler's severe-provider-error next-window rule.

If a campaign is genuinely eligible immediately, the Dashboard says it is `due now` instead of showing a timestamp in the past.

## Compatibility

No new database migration is required. The 0.9.32 Cloud output-headroom migration and all saved Discovery stage routes are retained unchanged.
