# ScoutBox 0.8.57 release notes

ScoutBox 0.8.57 is a no-migration UI, diagnostics-export and list-behavior release.

## Changes

- Diagnostic export is delivered as a compressed ZIP containing the anonymized JSON file. The export modal switches to `Downloading...` and disables Cancel/close while the request is active.
- Recycle Bin `Select All` now matches adjacent toolbar actions visually; the other list-view select-all controls were reviewed for the same issue.
- Address Book uses Name / Company itself as the edit control. Email opens the originating ScoutBox Opportunity or Hidden Lead when an origin is available and is plain text otherwise; it no longer uses `mailto:`.
- Hidden Lead detail suppresses zero-percent Summary/Company research progress badges and aligns Target/Search URL rows with the form fields.
- Opportunity and Hidden Lead fit controls expose a 0–5 human-readable scale and map it to the existing 0–100 stored score.
- Server-backed list searches no longer submit on every keystroke. Opportunity and Hidden Lead query matching is limited to relevant visible/list fields to avoid hidden-text false positives.
- Campaign run duration is removed from the campaign list and campaign XLSX because the recorded duration does not represent the complete discovery/analysis pipeline.
- Campaign and template Focus previews now truncate at whole-word boundaries.

No database migration, background telemetry, provider routing, discovery scheduling, or other system behavior is added by this release.
