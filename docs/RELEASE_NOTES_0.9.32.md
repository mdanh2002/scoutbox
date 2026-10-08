# ScoutBox 0.9.32

## Cloud Web structured-output reliability

Gemini 3-family models can spend a significant portion of `maxOutputTokens` on hidden reasoning. The previous Cloud Web defaults were too small for several structured Discovery stages, especially `jd_analysis` and `cold_contact`, which could leave only a few visible JSON tokens after reasoning and cause valid candidates to disappear during parsing.

0.9.32 increases the Cloud Web structured-output defaults while retaining per-stage control:

- URL discovery: 6000
- JD analysis: 3000
- First filter: 1800
- Company enrichment: 2200
- Freshness: 1600
- Page summarization: 2200
- Resume tailoring: 3600
- Email draft: 2400
- Application questions: 3600
- Cold contact: 3000
- Import inference: 4200

The provider-wide Cloud output cap still applies, and users can continue to edit individual stage caps manually.

## Truncation and malformed JSON recovery

Cloud Web no longer accepts a provider response as successful merely because the HTTP request completed. When a provider reports `MAX_TOKENS`, `length`, `max_tokens`, `incomplete`, or another supported truncation state, or when a JSON-only Discovery response is malformed/incomplete, ScoutBox:

1. retries the same model once with a larger output budget; then
2. uses the configured same-provider failover model if the retry is still unusable.

This matches the intended Primary/Failover routing semantics for structured Discovery work.

## AI Request diagnostics

Provider-truncated requests are now stored with Warning status and a clear warning message. The subsequent successful retry/failover remains visible as its own request, making it easier to identify output-cap problems without confusing them with the normal shortened table preview.

## Upgrade migration

Migration `0075_v0932_cloud_output_headroom` updates saved Cloud Web stage routes only when their output cap still equals the historical ScoutBox default. Deliberately customized caps are not changed.
