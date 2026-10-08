# v0.4.0 release notes

- Added **Source-Guided Discovery** (default) and **Cloud Web Discovery** modes.
- Source-Guided Discovery keeps CV-first search-provider URL discovery separate from JD analysis; downstream AI remains independently routable.
- Cloud Web Discovery uses OpenAI web search or Gemini Google Search grounding to return candidate URLs, bypassing ordinary configured search providers for that phase only.
- Added primary + fallback model/provider selection to every pipeline stage. Cloud URL discovery restricts both to configured cloud providers.
- Cloud-discovered URLs enter the same consolidation, duplicate/history checks, enrichment, geography-fit and ranking pipeline.
- Increased URL-discovery token defaults to 9,000 input / 2,500 output; all existing per-stage caps remain configurable.
- End-to-end Test Run now exercises the currently selected discovery strategy without creating opportunities.
- Added root recovery scripts `reset_admin_password.sh` and `reset_mail_defaults.sh`.
- The mail reset restores/activates GreenMail + Mailpit but preserves saved External Mail credentials.
