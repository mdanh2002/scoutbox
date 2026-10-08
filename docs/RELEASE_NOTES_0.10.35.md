# ScoutBox 0.10.35

Released 2026-09-07.

## Search Sources presentation

- Removed the long explanatory Direct/Local/Cloud paragraph from the Sources tab.
- Removed per-source capability prose from the source list; source rows now stay compact.
- A **Direct** badge is rendered only when the source has a configured dedicated adapter path that does not depend on a search-engine SERP, such as an API, ATS endpoint, feed/RSS path, community endpoint, or deterministic direct-page adapter.
- The Direct badge tooltip now gives the concise routing rule: ScoutBox can query that source without a search engine; Local also uses enabled search engines, while Cloud does not use ScoutBox search-engine source scraping.
- Removed the Preferred Sources explanatory paragraph. The controls and behavior are unchanged.

## Address Book

- Address Book Summary source links now use the same inline open-link icon and visual treatment as Opportunities and Hidden Leads, while remaining positioned immediately after the summary text.
- A compact green **200** health badge now appears immediately after that Summary hyperlink icon when the Address Book contact's checked company/email domain returns HTTP 200.

## About ScoutBox

- Replaced **Useful starting points** with **Discovery Mode**.
- Discovery Mode briefly explains Local AI Discovery versus Cloud Web Discovery, including local hardware/Ollama versus remote API-token requirements, benefits and tradeoffs, and the installation's current non-secret discovery configuration.
- Current configuration reports the selected discovery mode plus a concise runtime/source summary without exposing credentials.
- Added contextual links to Candidate Profile, Engagement Preferences, Search Sources, Campaigns, Opportunities, Hidden Leads, Applications & Outreach, and AI & Discovery instead of duplicating them in a standalone link card.
- Configuration guidance now explicitly explains remote/cloud API setup using OpenAI, Gemini, or OpenRouter with an API token and model.

## Troubleshooting reference

- Restored the Docker/Celery status and log commands under **Troubleshooting Tips** (`docker compose ps`, service logs, Django checks/migrations, and Celery inspect commands).
- Kept the old **Status, logs and recovery** subsection label hidden; the commands sit directly under Troubleshooting Tips.
- Kept **Common data checks** as a separate flat subsection after the operational commands.
- Removed the verbose paragraph beginning “These read-only Django ORM examples…” while retaining the examples themselves.

## Discovery behavior

No acquisition-routing behavior changes in this release:

- Local AI Discovery continues to run direct-source adapters and configured search-engine discovery additively.
- Cloud Web Discovery continues to allow dedicated direct adapters plus provider-native Cloud Web research while bypassing ScoutBox search-engine source scraping.

No database migration is required for 0.10.35.

Routine future releases increment the patch component on the 0.10.x release line.
