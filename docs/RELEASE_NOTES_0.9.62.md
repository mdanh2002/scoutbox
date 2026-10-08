# ScoutBox 0.9.62

## Manual Cloud filter reliability

- Manual Opportunity and Hidden Lead Cloud+Internet filters now use dedicated token headroom: 6,000 input tokens and 4,000 output tokens, without changing the routine Discovery first-filter caps.
- Gemini grounded filtering preserves provider-reported usage and diagnostics even when the HTTP request succeeds but produces no visible final response. AI Requests now retains finish reasons/messages, prompt/candidate/thought token counts, response/model identifiers, search-query counts, HTTP status, thinking mode, and whether JSON MIME was requested.
- Empty Gemini grounded responses are retried once on the same user-selected model. The retry uses `minimal` thinking and removes forced `application/json` response MIME; ScoutBox still validates/extracts the JSON object itself.
- The manual filter circuit breaker stops the batch after three consecutive empty-response attempts across the selected provider/model, preventing a broken provider path from consuming the remainder of the batch.
- A successful retry resets the empty-response streak. Other non-empty failures also break the streak.
- Automatic-stop details are retained in the Background Work result and included in the filter completion/failure email.
- No database migration is required.
