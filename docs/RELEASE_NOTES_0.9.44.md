# ScoutBox 0.9.44 Release Notes

## Gemini Auto-detect cost control

- Routine Gemini Auto-detect routes now use `gemini-3.1-flash-lite` with `gemini-3.5-flash-lite` as the documented fallback.
- Resume/CV tailoring is the only automatic Gemini stage that may use full Flash (`gemini-3.5-flash`) as primary; its fallback remains Flash-Lite.
- Chatbot automatic Gemini routing and OpenRouter Gemini automatic routing use the same Flash-Lite-first policy.
- Generic provider Automatic model resolution also prefers stable Flash-Lite before full Flash.
- Manual provider/model selections are unchanged.

## Resource Usage token-model filter

- Added a model multi-select beside the Token Categories heading.
- The menu includes Select all and requires at least two selected models when two or more models are available.
- Apply redraws the Token Usage multi-ring chart from the selected model set.
- The Token Usage heading reports whether the chart shows all tokens or selected models only.
- The server now supplies the complete provider/model token breakdown so filtering does not lose models that were previously folded into Other.

## Maintenance diagnostic billing data

- Diagnostic export format is now version 3.
- A new `billable_token_aggregates` section exports parallel, labelled reconciliation views from:
  - AI request logs (canonical per-call provider/model accounting),
  - UsageMetric telemetry,
  - CloudBudgetUsage daily counters,
  - retained PerformanceRun records.
- Aggregates include input, visible output, reasoning/thinking and total token counts where the source records them; provider/model/stage/day and token-usage-source breakdowns are included for AI request logs.
- Token accounting fields such as `reasoning_tokens` and `token_usage_source` are no longer incorrectly secret-redacted. Credentials and actual access/API tokens remain redacted.
- Parallel accounting sources may overlap and are explicitly labelled not to be added together.

## Provider call history

- Recent provider requests and recent provider errors are always-visible list tables; the expand/collapse wrappers were removed.

## Compatibility

- No database migration.
- No Opportunity discovery, eligibility, persistence, remote-status or freshness behavior changed.
- All previous 0.9.43 Company Info behavior and earlier UI fixes are retained.
