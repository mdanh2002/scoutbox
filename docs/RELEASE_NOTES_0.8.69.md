# ScoutBox 0.8.69 release notes

ScoutBox 0.8.69 focuses on Source-Guided query quality, Cloud Web reliability, quota visibility, AI-request lifecycle diagnostics, and several workflow/UI refinements. Existing campaigns, opportunities, leads, applications, uploads, provider credentials, and local routing are preserved.

## Discovery and search planning

- Cloud Web eligibility now depends on enabled provider configuration, credentials, and a resolved model. A stale or transient failed web-capability test is diagnostic evidence rather than a permanent Cloud Web lockout.
- Cloud Web runtime follows configured cloud-provider priority and tries the next eligible provider/model when a live grounded/web request fails. Cloud Web research prompting and campaign/profile context remain otherwise unchanged.
- Source-Guided query generation is now campaign-role anchored. The configured campaign role cannot be displaced by unrelated CV skills; realistic role-title aliases rotate across searches.
- Optional local Ollama query shaping proposes role aliases and compact opportunity/context wording. Deterministic aliases and context remain available if Ollama is unavailable, so search never depends on the helper model.
- Source-Guided queries draw from broader active-CV evidence plus high-, medium-, and low-priority preference text and engagement/company-size settings. Remote wording rotates instead of being appended blindly to every query.
- Enabled Custom Domains receive explicit `site:<domain>` searches. Configured source domains also receive a rotating share of `site:` searches.
- The legacy Specialist/custom, Feeds/announcements, RSS/Atom, and Europe/international catalog sections are removed. Welcome to the Jungle moves to Public community / social sources. Custom Domains remain the operator-controlled custom-site mechanism.

## Limits, diagnostics, and AI Requests

- Search-provider quota popups show actual used/capacity/remaining/reset values and per-provider breakdowns. Cloud AI limit popups show the same real daily usage information.
- Healthy/in-budget quotas use a brighter green borderless usage glyph. The amber exclamation mark appears only when a quota is actually exhausted/exceeded.
- AI Requests gains lifecycle states: Queued, Running, Completed, and Failed, with a dedicated queued icon and Status filter. Background AI work is represented while waiting/running so Task Type filters can expose queued work.
- The top-right Last 5 Errors preview continues to diversify by component/provider and now bolds the component label before the error detail.

## Workflow and UI

- Opportunity and Hidden Lead detail actions use a larger **Save Changes** button and return to their list after saving.
- Applications/Outreach Details **Save Changes** returns to the list with a visible success notification. Email & Application **Save Draft** remains in the editor and retains draft/IMAP behavior.
- Dashboard ScoutBox Activity progress rows use a consistent label/progress/value grid so utility AI rows align with campaign rows.
- Resource Usage now reports **ScoutBox Disk Used**, counting only the database, uploads/media, application files, and ScoutBox runtime files. Ollama model storage and unrelated host/Docker/system storage are deliberately excluded from the ScoutBox footprint.
- The shared-schedule hint is placed directly inside the Schedule section below the schedule controls.
- Production LLM prompts have been reviewed to remove unnecessary product-internal jargon where the model only needs a plain task description.

## Migration

Migration `0039_v0869_ai_request_status_source_cleanup.py` adds the AI Request lifecycle status and removes/moves the retired built-in Search Source catalog entries. User-configured Custom Domains are not removed.
