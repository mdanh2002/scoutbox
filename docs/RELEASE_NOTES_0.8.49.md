# ScoutBox 0.8.49

0.8.49 is a focused corrective release on top of 0.8.48.

## Chatbot

- Fixes the **Test Chatbot** browser action by giving the AI configuration page a self-contained HTML-escaping helper.
- Test Chatbot sends the hard-coded ScoutBox question directly to the exact provider/model currently selected in the form and displays either the actual answer or actual provider error in the popup.
- Stable ScoutBox product/navigation help is resolved before live database context is built, so questions such as where deleted items go remain available even when an optional live-context query is unhealthy.
- Live-context collection is fail-soft and the Chatbot endpoint remains a JSON 200 response for recoverable context/model failures rather than surfacing a generic network-level unavailable state.
- Model prompts include only the most relevant portal-guide entries to leave more context budget for useful live ScoutBox data.

## Test Discovery

- When URL discovery resolves to a web-capable Cloud provider (OpenAI, Gemini or OpenRouter), the Test Discovery input is treated as user intent and expanded into a complete profile-aware research instruction.
- The Cloud model chooses a small set of useful native searches itself rather than receiving the user's text as one raw search-engine query.
- The Test Discovery dialog shows the effective Cloud provider/model and explains that the request is expanded before submission.
- Discovery Summary records and displays the expanded Cloud research instruction.
- Local/Search Source Test Discovery remains unchanged and continues using the selected search engine.
- Existing Cloud AI safety limits continue to apply to diagnostic requests.

No new database migration is required.
