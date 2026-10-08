# ScoutBox 0.9.26

## Gemini Discovery Auto-detect progression

Cloud Web Auto-detect now assigns Gemini models per Discovery stage instead of using a coarse fast/balanced/heavy jump:

- `url_scrape`, `first_filter`, `freshness`: Gemini 2.5 Flash / Gemini 2.5 Flash-Lite.
- `company_enrichment`, `page_summarization`: Gemini 3.5 Flash-Lite / Gemini 3.1 Flash-Lite.
- `jd_analysis`, `cold_contact`: Gemini 3.5 Flash / Gemini 3.5 Flash-Lite.
- `email_draft`, `cv_tailoring`: Gemini 3.6 Flash / Gemini 3.5 Flash.
- `question_answers`, `import_inference`: Gemini 3.7 Flash / Gemini 3.6 Flash.

The 3.1 text fallback intentionally uses the stable `gemini-3.1-flash-lite` endpoint. OpenRouter's Google/Gemini defaults mirror the same stage mapping with `google/` prefixes.

Auto-detect remains metadata/documentation-driven and does not probe the provider. Manual Cloud model dropdowns remain based on the provider-returned catalogue and are not filtered by this preset map. Use Test Selection for live validation.

No database migration is required for 0.9.26.
