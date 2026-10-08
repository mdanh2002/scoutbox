# ScoutBox 0.8.71 Release Notes

ScoutBox 0.8.71 is a corrective release focused on Cloud Web execution integrity, remote-only opportunity quality, concrete opportunity URLs, evidence resolution, cancellation safety, and Post Age presentation.

## Discovery and routing

- Cloud Web is a hard execution mode. No automatic `cloud_web -> source_guided` mutation remains in provider saves, settings rendering, campaign launch, or the worker.
- Campaign runs snapshot `discovery_mode`; Cloud runs preflight Cloud routing directly and bypass local/Ollama readiness and local query planning.
- Cloud research runs one role per pass and keeps technologies/profile skills separate from the role title.
- Test Discovery uses a single Role focus and no longer sends product-internal ScoutBox wording to the research model.
- Cloud Candidate Requirements include structured engagement, company-size, pay, and hiring-process preferences.

## Opportunity eligibility and evidence

- Remote work is a persistence requirement. Hybrid, on-site, unresolved, and weakly verified remote candidates are rejected.
- Generic company/ATS boards cannot be stored as Opportunities. The Cloud resolver must establish an item-level role/project URL; ingestion contains a second defensive item-URL check.
- Cloud verification resolves Remote, Post Age, Fit and current status with a grounded follow-up request before persistence.
- Cloud Post Age evidence is reused directly and does not route through local freshness AI.
- A Best date within +/-1 calendar day of today is hidden unless the specific item itself explicitly states its posted/published date. Raw researched dates remain in Opportunity Evidence for audit.

## UI and operations

- Post Age refresh visibly shows progress and failure/success state; unknown cards no longer show a duplicate question mark.
- Search Activity is search-engine request traffic only. Cloud Web requests stay under AI Requests.
- Cloud source names are shortened to Gemini, OpenAI and OpenRouter.
- Provider configuration shows the actual Last tested timestamp; Configure Cloud priority uses normal enabled-button styling.
- Stop requests are timestamped and a scheduler watchdog finalizes stale Stopping runs after a three-minute grace period. Compare-and-set completion prevents a late worker from reviving a stopped run.
- Run History shows the execution path. Last 5 Errors shows relative timestamps.
- Resource telemetry provides percentage, request and token Y-axis scales and distinct series colours.

## Upgrade

0.8.71 introduces no database migration. Use the normal ScoutBox upgrade/restart procedure and preserve the existing `.env` and Docker volumes.
