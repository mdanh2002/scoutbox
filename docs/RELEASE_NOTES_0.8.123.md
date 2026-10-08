# ScoutBox 0.8.123

This release refines the three high-volume history toolbars and simplifies Local AI Discovery optimization.

- **Search Activity / AI Requests / Audit Trail:** bottom toolbars now use three stable zones: Rows-per-page + Export on the left, matching item count centered, pagination on the right.
- **Top filters:** Range, From, To and Apply are aligned to the right of the top toolbar on those three pages.
- **Local AI Discovery:** removes the visible **Auto Select Local** control. **Optimize for Local** is now the single automatic-local preset and clears explicit primary/fallback stage models.
- **Automatic Ollama selection:** prefers a capable installed model from 4B through 12B when possible. If the configured Ollama default is itself in that range, it remains the primary preference. Sub-4B models are used only when no 4B–12B installed model is available.
- **GPU warning:** Optimize for Local warns when ScoutBox cannot confirm a usable local GPU; the automatic selections can still be reviewed and saved.
- No database migration is added.
