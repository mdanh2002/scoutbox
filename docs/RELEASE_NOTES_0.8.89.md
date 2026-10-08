# ScoutBox 0.8.89

ScoutBox 0.8.89 is the corrected maintenance release based on 0.8.87, including the startup hotfix and the full post-0.8.87 maintenance change set. It does not add a database schema migration.

## Reporting, exports and diagnostics

- **Search & Limits → Restore Defaults** now reads from the same canonical default map used by model/form defaults, including the 0.8.87 Cloud limits.
- The rolling 24-hour digest is intentionally compact: each Opportunity, Hidden Lead and Address Book item is represented by time found plus a concise name; application changes, major errors and usage/limit summaries are similarly condensed. SMTP uses a formatted HTML version with a plain-text fallback.
- Diagnostic export supports **Last 24 hours**, **Last 3 days** and **All available data**, including persisted Chatbot history.
- AI Requests JSONL export is packaged as a compressed ZIP to reduce transfer size.
- Completed AI-request rows with no visible output are corrected to failed/error state, and new provider calls reject empty output before being recorded as successful.
- Dashboard diagnostic details include PostgreSQL, Redis and Ollama version information when those services expose it. The Diagnostics heading no longer links to Configuration.

## Campaign activity and search liveness

- Search-provider waits/retries refresh the CampaignRun heartbeat without artificially advancing the progress percentage. Dashboard **Possible stall** and the stall watchdog now use this liveness signal so an active provider retry is not treated as an abandoned run.
- Dashboard Recent Campaigns uses explicit full-width column sizing, including an unconstrained First / Last timestamp column.

## Resume, chat and maintenance UI

- Individual Resume template generation and bulk **Auto-create Campaign Templates** use ScoutBox internal modals rather than browser alert/confirm dialogs; the bulk action receives clearer top spacing.
- Ask ScoutBox safely converts mentions of specific Opportunities, Hidden Leads and Applications into direct title/name links. Separate action buttons remain reserved for major pages such as Dashboard or list views.
- Hidden Lead detail toolbar actions have consistent dimensions.
- Opportunity detail removes the redundant **Open Role** action; Source URL remains available.
- Blacklist replaces **Add Item** with the compact `+` action and places it after **Delete Selected**.
- The obsolete Maintenance action for recycling Cloud Web-generated Hidden Leads and Address Book contacts is removed.

## Data presentation and readiness

- Plain-text contact/email fields decode HTML entities and URL-encoding artifacts such as `%20`, `%40` and `&amp;` before validation/display; genuine URL fields are not indiscriminately decoded.
- First Run Readiness marks AI runtime ready when a local macOS/NVIDIA accelerator is detected or a Cloud AI route has been configured and successfully tested. Cloud credentials that exist but have not passed a test use an informational state; no local accelerator and no Cloud credentials uses a warning state.
- A Poor Fit classification with Low confidence is shown as an uncertainty question mark while preserving the underlying stored score/classification.

## About ScoutBox

- **Overall System Architecture** now carries a left-side architecture icon.
- The architecture section is stacked to avoid empty side-column space: the high-level system-flow diagram comes first, followed by a technical component/deployment diagram showing Django/Gunicorn, PostgreSQL, Redis, Celery Beat/worker, Ollama, Cloud AI, search/page services, mail integrations and persistent storage, plus concise engineering notes.
