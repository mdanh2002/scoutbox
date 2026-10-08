# ScoutBox 0.9.55

## Manual filter second-opinion workflow

- Opportunities and Hidden Leads selected filters now open a provider/model chooser instead of silently reusing the Discovery first-filter route.
- The default prefers Gemini Cloud with `gemini-3.5-flash-lite` when that credentialed route is available, then another usable Cloud route, with Ollama retained as an explicit local option.
- Cloud routes expose **Enable Internet Search**, enabled by default. The option is disabled for local/Ollama models.
- Web-enabled filtering remains anchored to the selected record's company, role and URL and uses current public sources only to verify that exact record; it does not discover substitute opportunities.
- Only one manual Opportunity/Hidden Lead filter can run at a time. Both the UI and server enforce this across the two lists, with guidance to stop the active job from Dashboard > Background Work.
- The Dashboard section formerly labelled `ScoutBox activity` is now **Background Work**.
- The most recent completed filter is retained and shown directly on the relevant Opportunities or Hidden Leads screen, including route, web-search state, outcome counts and per-entry decisions/reasons.
- Filter completion/failure sends a notification to the logged-in account email. The send attempt is stored as a notification `MailEvent`, so it remains visible under Email History; configuration/delivery failures are retained there as failed attempts.

No database migration is required for 0.9.55. Existing BackgroundJob and MailEvent storage is reused.
