# ScoutBox 0.8.114

## Chatbot configuration
- Renames `Save chatbot` to `Save config`.
- Widens the Chatbot label column so provider/model/token controls and the internet-research checkboxes align more cleanly with the test-action row.
- Primary/secondary routing and failover behavior are unchanged.

## Chat export
- Replaces the browser HTML transcript export with a native Word `.docx` export.
- Preserves timestamps, User/ScoutBox separation, headings, bullet/numbered lists, bold/italic/underlined/code-style inline text, inline web/ScoutBox links, action links, and the provider/model source line for ScoutBox answers.
- Relative ScoutBox links are converted to absolute links using the current ScoutBox host.
- The export remains transient and does not add server-side chat persistence.

## Resource Usage and Dashboard
- Adds `Last 3 days` before Week on Resource Usage and Dashboard Discovery Activity.
- Resource Usage uses a true rolling 72-hour window. Dashboard renders the same 72 hours as twelve 6-hour buckets.
- Cloud Usage now contains only six quota/safety gauges: Cloud AI Requests, AI Web Search Queries, Input Tokens, Output + Reasoning, Passive Enrichment, and Page Recovery.
- Removes the standalone Output Tokens row from Cloud Usage; Output Tokens remains available in the Resource Usage metric cards above.
- The six Cloud Usage gauges use a balanced 3-by-2 desktop layout with responsive fallbacks.

## Email Configuration
- Left-aligns `Save folder assignments` under the IMAP folder selectors.
- Existing asynchronous IMAP refresh/detect/test-email behavior is unchanged.

No database migration is required. Migration `0069_v08111_chatbot_source.py` remains the latest migration.
