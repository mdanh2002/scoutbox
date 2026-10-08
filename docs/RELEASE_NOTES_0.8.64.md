# ScoutBox 0.8.64 release notes

Released on 2026-08-23 16:43:00.

ScoutBox 0.8.64 is a focused provider-testing and UI consistency release. Automatic Cloud provider priority and all existing provider-routing behavior are preserved.

## Changes

- Provider cards use aligned field widths; Default model matches API-key width and Ollama Base URL keeps Validate Config aligned with cloud providers.
- Automatic provider tests now choose a common available model without changing the saved Default model.
- Provider test results are shown in a completion popup with token/response data on success and detailed troubleshooting diagnostics on failure.
- Saved cloud credentials are reused for Validate Config when the API-key field is blank after returning to the page.
- Chatbot Test uses a non-modal Testing ... progress state and disables Save until the result is ready.
- Address Book Mark as… is selected-only, confirmation-free, positioned beside Search, and opening the contact editor marks the row Seen. New rows use unread-style text colour without bolding.
- Standard action buttons receive hover/pressed feedback.
- Performance Lab Other performance tests is always expanded.
- First Run Readiness removes optional labels and aligns the AI runtime detail text.

No database migration is included.
