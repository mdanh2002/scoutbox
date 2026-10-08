# ScoutBox 0.8.45

0.8.45 is a corrective release on top of 0.8.44.

## AI readiness and campaign launch

- Fixed a false **AI compute unavailable / Required local model is unavailable** state when the actual Ollama stage models were installed and Test Selection had passed. Local readiness now checks usable local GPU + Ollama runtime + installed models rather than requiring the provider-level default model to match the routed models.
- A current successful Test Selection route validation can establish cloud-provider readiness as well as a direct provider test. No specific cloud provider is required.

## Provider-neutral Cloud safety

- Removed the shared OpenRouter-only daily USD safety setting and its Resource Usage display. Global Cloud safety is provider-neutral and remains enforced through request, native-web-search, input-token, output/reasoning-token, campaign-run, passive-enrichment and recovery limits.
- Provider-reported monetary cost, when available, remains request-level telemetry in usage metadata; no vendor-specific cost counter is used as a shared Cloud AI safety control.

## Resource Usage

- Moved the resource-chart peak token/request annotations inside the plot so they no longer clip at the right edge.
- Added right-side breathing room to the **Hard Cloud AI safety limits reset daily** note.
- Added **Token Providers** below Token Categories: a provider pie/donut plus provider totals for Ollama, OpenAI, Gemini, OpenRouter, and any other provider names actually present in UsageMetric data.

## Hidden Leads

- Removed the duplicate read-only Contact Email display from the lead popup; the editable Contact email field remains.

## Migration

- `0033_v0845_provider_neutral_readiness_usage.py` removes the obsolete OpenRouter-only daily cost-limit setting and the vendor-specific daily OpenRouter cost counter.
