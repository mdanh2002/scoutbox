# ScoutBox 0.11.117

ScoutBox 0.11.117 removes the fixed 12-query-per-provider ceiling added in 0.11.116.

## Search traffic correction

- Local source-guided campaign search now uses the configured `queries_per_provider` value as its starting allowance instead of clamping every provider to 12 queries.
- The `SCOUTBOX_PROVIDER_QUERY_HARD_CAP` clamp is removed.
- Existing adaptive provider health logic remains active. Recent zero-yield or high-error providers can still be reduced to recovery probes, while productive providers can use the configured allowance.
- Existing search-stage time budgets, consecutive-error stop handling, market compatibility checks, and test-mode limits remain unchanged.

This restores operator-configured traffic headroom without reverting the discovery-quality improvements introduced in 0.11.116.
