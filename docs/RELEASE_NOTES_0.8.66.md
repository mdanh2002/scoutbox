# ScoutBox 0.8.66 release notes

ScoutBox 0.8.66 is a search resilience, campaign context, attribution, and macOS telemetry release. Existing campaign/opportunity/lead/application data is preserved.

## Search discovery and quotas

- Preferred Initial providers are now preference-first, with eligible enabled fallback providers used when preferred providers are unavailable or exhausted.
- A fully exhausted provider pool stops a run with `provider_daily_budgets_exhausted` instead of reporting a successful empty campaign; the automatic scheduler waits for reset instead of launching repeated empty runs.
- Provider-selection diagnostics are stored with campaign results.
- Default daily budgets are 5,000 requests per public/no-key provider and 500 per API-key provider. Existing installations still on the legacy default 100 are migrated to those split defaults; explicitly customized values are preserved for both modes.
- Per-provider daily overrides accept up to 10,000 requests/day.
- Default discovery breadth is 100 query variants/attempt, 100 queries/provider/attempt, and 100 results/query. Campaign-specific rotation accepts up to 100 queries.
- Search Sources shows quota-consumption/reset hints and uses a yellow borderless exclamation glyph after consumption.

## Campaigns and usage attribution

- Search-provider and Ollama usage metrics inherit campaign and campaign-run context.
- Search Activity refreshes every five seconds while visible and keeps provider configuration tests separate from campaign searches.
- Campaign Local Token Usage uses direct attribution for new data and a conservative, unambiguous AIRequestLog fallback for older local history.
- Campaign Detail adds a 2,000-character Description field that is informational only.
- Run Now uses Notes for local/source-guided discovery and Custom instructions for Cloud Web discovery. Notes never affect prompts.
- Cloud Custom instructions augment saved criteria and support Keep until with a 48-hour default. Retained instructions flow into subsequent/scheduled Cloud runs until expiry; a newer explicit instruction supersedes the prior retained one. Campaign lists and Run History show the context and expiry.

## Diagnostics and UI

- macOS host telemetry starts through `bash` so lost archive execute bits cannot silently prevent CPU/memory/GPU host reporting. Apple Silicon GPU identity remains visible when utilization counters are unavailable.
- Address Book Source cells are icon-only links, and obvious multi-word email usernames can supply a missing human name while generic mailbox names remain excluded.
- Gemini configuration testing allows 256 output tokens, uses low/minimal thinking only for that connectivity test where supported, and reports prompt/visible/thinking/total tokens, finish reason, HTTP status, and provider response/error details.
- Ollama provider configuration fields are narrower and the Test configuration action is aligned with cloud provider actions.
- The Hidden Leads hashlib path is covered by the 0.8.66 targeted regression suite.

## Migration

Migration `0038_v0866_search_budgets_campaign_description.py` adds the split provider-budget settings and Campaign Description, and migrates only the legacy provider-budget configuration. It does not rewrite campaign, opportunity, lead, or application records.
