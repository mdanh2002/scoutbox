# ScoutBox 0.8.62 release notes

Released on 2026-08-23 15:52:00.

ScoutBox 0.8.62 is a Provider Configuration UI/workflow release with no database migration.

## Changes

- Provider Configuration is rendered in a fixed OpenAI → Gemini → OpenRouter → Ollama local order.
- Removed the separate Ollama local runtime card; installed Ollama model tags now appear inside the final Ollama provider section.
- Removed editable provider Test Prompt controls. Every provider Test uses a small built-in ScoutBox prompt.
- Cloud provider API key and Base URL are on the first row with an asynchronous **Validate** button. Validate checks the current on-screen credentials/URL without saving and retrieves the provider model catalogue.
- Default model is now a dropdown that always shows **Automatic**, including before validation. A successful Validate populates the dropdown with the models returned by OpenAI, Gemini, OpenRouter, or Ollama.
- Default model and Output token cap share the second row for cloud providers.
- Provider Test runs asynchronously against the exact current on-screen Base URL/API key/model and shows response text plus input/output token counts below the Test button. Cloud tests retain the existing web-research capability probe and cloud safety budgets.
- Provider rows no longer have individual Save buttons. One asynchronous **Save Provider Configuration** action persists all four provider sections at the bottom.
- Automatic Cloud provider priority logic is unchanged. Its section is visually compact: three short dropdowns share one row, the existing hint follows underneath, and **Save priority** is right-aligned below the hint and saves asynchronously.
- Existing stale per-provider POST handlers remain for backward compatibility, but the 0.8.62 UI does not use them.
- No database migration, discovery-routing policy change, scheduler change, or telemetry expansion is included.
