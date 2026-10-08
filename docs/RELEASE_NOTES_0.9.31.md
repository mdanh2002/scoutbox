# ScoutBox 0.9.31

## Discovery routing UI and Gemini Auto-detect

- Widened the Discovery Stage column so long names such as Company enrichment, Page summarization and Application questions remain readable.
- Gemini Cloud Web Auto-detect no longer starts from the retired/unavailable 2.5 Flash-Lite lane.
- High-volume stages now start with Gemini 3.1 Flash-Lite and fail over to Gemini 3.5 Flash; later stages step through 3.5, 3.6 and 3.7 as complexity rises.
- OpenRouter's Gemini presets mirror the same Gemini 3-family progression.

## Chatbot Test Selection

- Replaced separate Test Primary / Test Secondary buttons with one Test Selection action.
- Test Selection validates Primary and Secondary sequentially, keeping the two per-model status icons and last-tested timestamps.
- Model dropdowns keep the same visible width as the provider/token fields, with the validation icon in its own lane to the right.

## About ScoutBox polish

- Replaced the About export glyph with a cleaner Word-document icon while keeping the control icon-only and borderless.
- Common data-check descriptions now sit above each command box, allowing every command example to use the full content width.

No database migration is included in 0.9.31.
