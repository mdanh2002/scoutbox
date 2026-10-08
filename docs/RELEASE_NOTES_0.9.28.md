# ScoutBox 0.9.28

## Token Usage cleanup

- Removed the older simple Token Providers pie chart from Resource Usage.
- Renamed the token-provider/model section and detailed model visualization to **Token Usage**.
- Retained the Provider / Tokens / Share detailed table and the model-level concentric rings for total, input, output and reasoning tokens.
- Live refresh and date/provider filtering continue to update the provider table and model-level Token Usage chart.

No Discovery routing, model Auto-detect behavior, database schema, or usage aggregation is changed in 0.9.28. This is a presentation cleanup over the existing UsageMetric telemetry.
