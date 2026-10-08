# ScoutBox 0.8.1 architecture

ScoutBox is a Django application with PostgreSQL, Redis/Celery, GreenMail, Mailpit and optional host-native Ollama/cloud AI/search integrations.

## Runtime roles

- `web`: Django/Gunicorn and the only container that performs migration/bootstrap work.
- `worker`: Celery long-running campaign/import/test tasks.
- `beat`: scheduled discovery/mail/tracking/digest triggers.
- `db`: PostgreSQL persistent application state.
- `redis`: Celery broker/state transport.
- `greenmail`: internal-development application IMAP mailbox.
- `mailpit`: development notification SMTP and UI.

## Upgrade/schema design

`portal/0001_initial` is the migration-safe schema introduced after the old syncdb releases. Startup applies Django auth first, runs `prepare_legacy_schema`, then `migrate --fake-initial` so a v0.7.2-era schema can be adopted without deleting data. 0.8.1 adds normal migrations for workflow/UI data structures.

## Long-running work

Campaign runs and application-history inference are represented by `CampaignRun`/`BackgroundJob` rows and execute in Celery. This lets the web request return quickly, gives the Dashboard observable progress, and lets active campaign runs receive a stop request at safe checkpoints.

## Discovery modes

Source-Guided Discovery uses configured search adapters and source presets, then retrieves/analyzes candidate URLs. Cloud Web Discovery delegates URL discovery to a configured OpenAI/Gemini route; source-provider selection is preserved but inactive for URL discovery in that mode.

## Chatbot

The chatbot is read-only. Its prompt combines a portal-wide screen guide with bounded live snapshots of opportunities, prepared applications, applied roles, campaign/search state, email configuration (without passwords), AI routing (without API keys) and system settings. Common configuration-location questions have a deterministic help path before an LLM call.

## Credential boundaries

The release number is read only from `VERSION`. Deployment/host/search-provider environment credentials are read from `.env`. Existing portal subsystems that already use encrypted application storage (for example configured mail/AI/ToughDev connector secrets) remain encrypted and are never returned by the chatbot.
