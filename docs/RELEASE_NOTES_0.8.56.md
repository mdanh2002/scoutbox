# ScoutBox 0.8.56 release notes

ScoutBox 0.8.56 is a diagnostics and workflow refinement release. It requires no new database migration.

## Diagnostic export

Configure → Maintenance now includes a green, read-only **Export Diagnostic Data** action. The JSON export supports the last 7, 30, 90 days or all retained data and is intended for offline analysis together with the ScoutBox source code.

The export uses only data ScoutBox already retains. It correlates campaign definitions/runs, opportunity and Hidden Lead outcomes (including user-deleted records), applications/outreach, recycle-bin state, blacklist, search-provider statistics and run selections, AI request logs, cloud usage, resource samples, current non-secret configuration, audit history, diagnostics/performance jobs and retained errors. Derived summaries make campaign effectiveness and provider/failover patterns easier to inspect without adding new telemetry or changing discovery behavior.

Candidate Profile name, application email and phone fields are omitted. Matching applicant/admin personal values are redacted from retained text, and credential/token/password fields are always redacted. Company data and public company contacts are preserved.

Container/stdout errors that ScoutBox never persisted cannot be reconstructed by the export; retained rare errors such as dependency/import failures remain included when present in database-backed logs.

## Interface/workflow refinements

- Resource Usage has a top margin between the sticky date toolbar and the metrics grid.
- Blacklist adds a Scope filter after a narrower search input, including filter-aware XLSX export/paging.
- Recycle Bin adds a confirmed bulk Add to Blacklist action based on selected rows' domains and labels; recycled records remain untouched.
- Address Book name/company links return to originating Opportunity records when recoverable from existing URL/email/company data.
- Opportunity Detail hides the technical Extracted Facts/raw JSON presentation while leaving the underlying data unchanged.
- Hidden Leads now use a dedicated detail page with sticky Save, Prepare Outreach and Blacklist actions, replacing the list popup.
