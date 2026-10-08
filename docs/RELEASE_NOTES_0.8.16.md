# ScoutBox 0.8.16 release notes

0.8.16 is a reliability and review-workflow release over 0.8.15.

## Highlights

- Resource Usage no longer depends on a successful Ollama diagnostic call, refreshes charts and live resource labels every 15 seconds, shows memory in MB/GB on a dedicated axis, and exposes raw token/provider values on hover.
- Host telemetry remains best-effort and non-fatal: macOS uses the host bridge and native system tools; Linux can use `nvidia-smi`; missing tools produce unavailable values rather than crashing ScoutBox.
- Search-engine queries strip unary negative/exclusion syntax before provider calls. Migration `0014_v0816_reliability_read_state` also scrubs saved campaign criteria, run plans/results, diagnostic/performance payloads, usage metadata, profile scope and saved filters so legacy `generic full stack` clauses cannot persist into future runs.
- Confirmed 404/410 and aggregate/listing pages cannot be admitted as one Opportunity. Supported aggregate pages are expanded into individual target URLs for validation and processing.
- Inbox, Sent and Drafts are re-read during IMAP sync; classification is body-first (including forwarded content), existing Application records are reconciled before proposing imports, and scan totals/folder errors are shown in Applied Role Import.
- Dashboard attention, readiness and host diagnostics; Market Studies summaries/company/country handling; Campaign status; application read state; Search Sources request/error history; Maintenance hints; and list/table clarity receive additional polish.

## Upgrade

Keep your existing `.env` and Docker volumes. Apply the package, then run the normal ScoutBox restart/upgrade script so migrations execute and host telemetry is restarted. Migration 0014 performs the saved-query cleanup during upgrade.

## Validation

The release package is statically verified with Python byte-compilation, shell syntax checks, package-content checks, and targeted source/template regression assertions. The build environment used for packaging does not include Django, so `manage.py check` is not part of package verification.
