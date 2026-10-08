# ScoutBox 0.8.70 Release Notes

ScoutBox 0.8.70 is a corrective release focused on Discovery Method switching, diagnostics/list usability, company-research query quality, and opportunity evidence classification.

## AI & Discovery

- Fixes asynchronous Discovery Method switching: the selected value is added to the request before the selector is disabled, preventing Cloud Web from silently posting no mode and falling back to Source-Guided.
- Cloud Web continues to use automatic provider/model priority and live fallback; Source-Guided keeps the local Ollama stage table.
- Test Discovery is pre-populated with profile-derived keywords.
- Test Selection immediately shows queued state and persists stage-by-stage progress/results while the worker is running.
- Ollama Test configuration is aligned in the local provider heading; AI Requests status filtering is widened slightly.

## Search Sources and list views

- Search-source controls now have three visual states: information-only, healthy quota, and exhausted quota.
- Existing list filters display per-option item counts. No new filters are introduced.
- Mark-all Read/Unread/New/Seen choices are removed from list controls; selected-item actions remain.
- Opportunity provider/query provenance has a repeat-public-search arrow matching Search Activity.
- Search Activity retains the five-minute refresh and current page while receiving a small width adjustment to avoid needless horizontal scrolling.

## Company research

- Source-Guided company research rotates bounded searches across official/about, products/technology, engineering/team, leadership, hiring, projects/partners, credibility/news, and registration intents.
- A configured local Ollama model may propose improved query wording; deterministic queries remain the fallback.
- Cloud-native company research keeps its existing grounded Cloud Web route.

## Post Age, Remote and Fit

- Post Age is based on cleaned page text interpreted by the configured model plus a cautious HTTP `Last-Modified` signal. Implausibly old/future header dates and headers suspiciously close to request time are ignored.
- The UI shows a compact age range (`≤ 7 days`, `≤ 1 month`, `≤ 3 months`, etc.) and the best exact date. Confidence is represented by text colour instead of a face/smiley icon.
- Opportunity Detail now shows Remote classification directly.
- Remote is classified from the actual cleaned opportunity evidence with structured states (`fully_remote`, `remote`, `hybrid`, `onsite`, `unknown`) rather than keyword filtering.
- Fit is classified by the configured model using the opportunity evidence plus candidate priorities and engagement preferences; previous discovery score is preserved if the classifier is unavailable.
- Company Info retains its confidence bar/percentage without a face/smiley indicator.

## Data compatibility

No new database migration is introduced in 0.8.70. Existing 0.8.69 migration `0039_v0869_ai_request_status_source_cleanup.py` remains part of the package. Existing campaigns, opportunities, leads, applications/outreach, credentials and uploaded data are preserved during normal upgrade.
