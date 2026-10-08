# ScoutBox 0.8.65 release notes

Released on 2026-08-23 17:30:00.

ScoutBox 0.8.65 is a focused provider-testing, search-activity, diagnostics, and UI consistency release. Automatic Cloud provider priority and all existing provider-routing behavior are preserved.

## Changes

- Provider Configuration removes **Validate Config**. **Test configuration** first validates/retrieves the provider model catalogue, refreshes the Default model choices, then runs the generation test. Automatic model testing remains supported.
- Cloud provider rows are aligned as API key/Base URL followed by Default model/Output token cap/Test configuration. Ollama keeps Base URL/Default model/Test configuration on one row.
- Provider test failure dialogs include phase, discovered-model count, input/output tokens, request/HTTP details, provider detail, and a safe truncated server response when available. Empty Gemini/provider responses now expose the returned response metadata for troubleshooting.
- Chatbot fallback model is a provider-aware dropdown, disabled until a fallback provider is selected. The complete Chatbot form is disabled while Test Chatbot is in progress.
- Search Activity includes Cloud Web search/grounding UsageMetric rows and new Cloud Web telemetry stores the existing request text/error in the same metric metadata used by the activity screen. Dashboard discovery Search counts include Cloud Web requests.
- Dashboard 24-hour errors are deduplicated into distinct error incidents rather than summing repeated low-level error counters. Recent Errors is based on timestamped recent failures and no longer links the date/time cell.
- Read/Unread changes in Opportunities, Hidden Leads and Applications no longer ask for confirmation.
- Sortable table headers have a minimum width and no-wrap behavior so sort glyphs do not drop below compact headings such as Scope.
- Button hover movement is removed while active/pressed feedback remains.
- Performance Lab renames **Other performance tests** to **Custom Test**. First Run AI-runtime detail gets only a small alignment nudge.

No database migration is included.
