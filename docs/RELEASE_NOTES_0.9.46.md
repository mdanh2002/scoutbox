# ScoutBox 0.9.46

## Gemini Auto-detect Primary / Failover order

- Routine Gemini Discovery Auto-detect now assigns `gemini-3.5-flash-lite` as Primary and `gemini-3.1-flash-lite` as Failover.
- This applies to URL discovery/scrape, JD analysis, first filter, company enrichment, freshness, page summarization, email draft, application questions, cold contact, and import inference.
- Ask ScoutBox Chatbot remains `gemini-3.5-flash-lite` Primary -> `gemini-3.1-flash-lite` Secondary.
- Resume/CV tailoring remains `gemini-3.5-flash` Primary -> `gemini-3.1-flash-lite` Failover.
- OpenRouter Gemini automatic routes mirror the same order.
- Generic Gemini automatic provider-test selection now also prefers 3.5 Flash-Lite before 3.1 Flash-Lite.
- Manual model selections and all non-routing behavior remain unchanged.

Saved user routing is not rewritten on upgrade. Run Auto-detect and Save once if the current saved routing was produced by 0.9.45.

No database migration is required.
