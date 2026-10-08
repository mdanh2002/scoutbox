# ScoutBox 0.8.47

## Activity and audit filtering

- Search Activity Provider and Outcome selectors now show full-dataset faceted counts.
- AI Requests Runtime, Provider and Task Type selectors show full-dataset faceted counts while keeping Local/Cloud as the high-level runtime category.
- Audit Trail adds an exact Action selector with counts; audit search/filter/export is server-side.

## Provider-explicit AI routing

- Discovery Method stays **Source-Guided** and is disabled when no Cloud AI provider/model is configured.
- Chatbot configuration now selects an exact primary provider/model and optional exact fallback provider/model; generic Cloud AI remains a reporting category, not an execution target.
- Automatic Cloud execution follows a configurable OpenAI/Gemini/OpenRouter provider priority. Explicit stage/bundle/fallback choices take precedence.
- Cloud Web URL discovery resolves to a specific web-capable provider/model and no longer invents a fallback merely because another Cloud provider is enabled.
- Provider tests persist model capability hints used by cloud research routing.

## Cloud research bundling

- Web-capable Cloud AI stages can own compatible downstream discovery work for their Primary or Fallback lane independently.
- A Cloud JD Analysis request can combine JD interpretation, relevance/ranking, company research, remote/engagement checks, application-process research, freshness/posting-age work and summary/evidence instead of issuing separate Cloud requests.
- Inherited routing controls are visibly marked **Bundled with…** and disabled while the upstream cloud owner is active; saved explicit selections are preserved for restoration/fallback behavior.
- Test Selection validates the effective request topology and marks inherited stages as bundled instead of repeating identical cloud tests.
- AI Request detail shows the compatible activities satisfied by a bundled cloud request.
- Source-Guided mode still gets initial URLs from configured search engines and applies cheap deterministic canonicalization/deduplication/blacklist/history/sanity checks before shortlisted candidates reach Cloud AI.
- **Hidden Leads bypass JD Analysis**. When Cloud Company Research is selected, one grounded Hidden Lead research request covers company context, actionability, realistic paid-work paths, contact/outreach evidence and lead summary where available.

## Campaign analytics

- Campaign Detail adds **Duplicates** and **Errors** charts.
- Campaign analytics now show six charts: Opportunities, Leads, Local Token Usage, Cloud Token Usage, Duplicates and Errors.
- All six charts share Hour / Day / Week / Month and From / To controls.

## Recycle Bin

- Deleting Address Book contacts moves them to Recycle Bin instead of hard-deleting them.
- Deleting Blacklist entries moves them to Recycle Bin instead of hard-deleting them; recycled blacklist entries no longer suppress discovery until restored.
- Address Book and Blacklist entries support Restore, Delete Selected and Empty Recycle Bin behavior.
- Recycle Bin adds **Item Info** with the most useful type-specific identifier, such as contact email/URL, opportunity/lead email or URL, and blacklist domain.

## Compatibility

- Migration `0034_v0847_routing_recycle_filters.py` adds cloud provider priority/capability state and soft-delete timestamps for Address Book/Blacklist records.
- Existing 0.8.46 provider-neutral Cloud AI limits, OpenRouter support, no-GPU portal operation, Ubuntu/NVIDIA runtime selection, VRAM telemetry, manual enrichment refresh, and Resource Usage analytics are retained.
