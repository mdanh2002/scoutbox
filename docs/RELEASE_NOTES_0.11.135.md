# ScoutBox 0.11.135

## Unified SearchAPI provider

- Search Sources now presents one **SearchAPI** entry under **Search APIs / SERP** instead of one visible row per SearchAPI engine.
- The unified SearchAPI dialog owns one shared API key and individual automatic-use toggles for Google Jobs, Google Web, Google Forums, Google News, ChatGPT Research, Google AI Mode Research, and Google Local / Employer Discovery.
- Google Jobs, Web, Forums, and News remain enabled by default on an existing enabled SearchAPI installation. ChatGPT Research, Google AI Mode, and Google Local are opt-in.
- Internal child sources remain separate so ScoutBox can keep per-engine routing, health, result-yield, error, and request telemetry.
- The Test Search control is a single desktop row: query, service dropdown, then **Test Search** immediately after the dropdown. Every SearchAPI service remains testable even when disabled for automatic ScoutBox use.
- The SearchAPI request/error history now includes a compact Service column, wraps long queries/errors, and no longer requires a horizontal scrollbar at normal dialog widths.

## SearchAPI AI research

- Added **SearchAPI · ChatGPT Research** for sparse, cited public-web research. It is not a replacement for ScoutBox's configured OpenAI, Gemini, OpenRouter, or Ollama generation/classification provider.
- Automatic ChatGPT Research is disabled by default and, when enabled, is limited to research-specific escalation such as blocked-listing rescue, original employer/ATS resolution, native community-signal corroboration, and difficult current public-web verification. Community corroboration only contributes evidence after ScoutBox independently fetches a returned source and confirms explicit hiring/careers language.
- Direct user-configured OpenAI/Gemini/OpenRouter credentials take precedence over automatic SearchAPI ChatGPT research.
- SearchAPI ChatGPT prompts are deliberately compact and public-evidence oriented; normal CV/application/profile generation flows are not routed through it.
- Added optional **Google AI Mode Research**, market-localized and disabled by default. It remains a Search Activity request rather than a direct ScoutBox AI-provider request.
- ChatGPT Research and Google AI Mode each default to a maximum of 10 automatic calls per day when enabled; both are additionally bounded by the shared SearchAPI daily limit.

## SearchAPI employer discovery

- Added optional **Google Local / Employer Discovery**, disabled by default.
- Google Local results are employer candidates, never vacancies by themselves. ScoutBox uses a bounded localized Google Web careers/jobs/hiring verification pass before a Local-discovered company can enter the Hidden Lead signal lane; normal relevance/actionability gates still decide retention.
- Existing explicit Discovery Market localization remains mandatory for market-aware SearchAPI engines so Google cannot silently fall back to US geography.

## Diagnostics and request accounting

- SearchAPI Google Jobs, Web, Forums, News, Google AI Mode, and Google Local attempts are written to **Diagnostics → Search Activity** with their individual SearchAPI service identity.
- SearchAPI ChatGPT attempts are written instead to **Diagnostics → AI Requests**, classified as **Cloud Runtime**. They are not duplicated in Search Activity.
- SearchAPI ChatGPT model names are prefixed with `searchapi-` (for example `searchapi-gpt-5`); if SearchAPI does not expose a model identifier, ScoutBox records `searchapi-chatgpt`.
- All SearchAPI services continue contributing to one shared provider request counter and shared daily limit.

## SearchAPI daily limit

- Added **SearchAPI daily limit** as the final setting under Search Sources → Schedule / Limit.
- Default: **500 requests/day**. Configurable range: **0–10,000**.
- The limit is shared across every SearchAPI engine; enabling more SearchAPI services does not multiply the allowance.
- Manual Test Search requests also count toward the shared daily usage figure.
- A limit of 0 blocks SearchAPI requests without deleting the saved credential or service preferences.

## Quota-pressure gauges

- Schedule / Limit speedometer icons now communicate percentage pressure against finite limits:
  - gray: unused / no meaningful finite usage,
  - green: greater than 0% and below 60%,
  - amber: 60% through 90%,
  - red: above 90%.
- Colors are percentage-based, so large absolute counters remain green when they are still well below their configured limit.

## Preserved behavior

- 0.11.134 community hiring-signal handling for Reddit, Hacker News, specialist forums, SearchAPI Forums, and SearchAPI News remains intact.
- 0.11.133 Global Coverage scheduling, worldwide market catalogue, localized SearchAPI Google Jobs/Web acquisition, multilingual ingestion, country provenance, and regional-board acquisition remain intact.
- 0.11.132 manual re-evaluation reliability and scope-dialog layout safeguards remain intact.

- SearchAPI location targeting now uses the free Locations endpoint as a cached internal canonicalization helper where available; lookup failure falls back to the explicit Discovery Market and never removes the market requirement.
