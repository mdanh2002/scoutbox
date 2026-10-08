# ScoutBox 0.9.45

## Chatbot Gemini Auto-detect

- Ask ScoutBox Chatbot Auto-detect remains restricted to Flash-Lite models.
- Gemini Chatbot Primary is now `gemini-3.5-flash-lite`.
- Gemini Chatbot Secondary is now `gemini-3.1-flash-lite`.
- OpenRouter Gemini Chatbot Auto-detect mirrors the same order with `google/` model IDs.
- Discovery, enrichment, filtering, summarization, drafting, Q/A and import inference keep the 0.9.44 cost-first policy: `gemini-3.1-flash-lite` Primary and `gemini-3.5-flash-lite` Secondary.
- Resume/CV tailoring remains the only automatic Gemini route allowed to use full Flash as Primary.
- Manual model selections are unchanged.

No Opportunity behavior, token/resource statistics behavior, maintenance export format, provider call-history behavior, database schema, or migrations are changed.
