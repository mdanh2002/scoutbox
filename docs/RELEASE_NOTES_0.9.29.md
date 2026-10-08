# ScoutBox 0.9.29

## Token Usage consolidation

- Removed the separate **Provider / Tokens / Share** summary table from Resource Usage.
- Kept the more accurate provider/model concentric Token Usage visualization.
- Integrated each model's share and total directly into its bold legend heading, for example `Ollama · qwen2.5:7b · 45.0% · 7.2M tokens`.
- Input, output and reasoning token totals remain directly underneath each model heading.
- Hover details, live refresh, date filters and provider filters are unchanged.

No database migration or AI/Discovery routing behavior changes are included in 0.9.29.
