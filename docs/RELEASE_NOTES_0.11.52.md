# ScoutBox 0.11.52

## Fixed

- Hidden Lead summaries no longer expose structured page-evidence section labels such as `[APPLICATION]`, `[QUALIFICATIONS]`, `[PAGE_TITLE]`, `[JOB_DESCRIPTION]`, or similar bracketed extraction markers.
- Existing Hidden Lead summaries containing those evidence markers are now treated as stale and enter the same deterministic repair path as other legacy/generic summaries. ScoutBox uses retained company facts or clean evidence-backed company prose when possible and otherwise shows `Summary pending.` rather than raw extraction text.
- The deterministic evidence fallback now understands section boundaries, excludes application/qualification/footer/navigation and other non-company sections, and applies a stronger business-context threshold to `PAGE_TITLE` material so article/tutorial text is less likely to become a company description.
- Hidden Leads list rendering no longer falls back to raw `lead.evidence`. Raw evidence remains available for research/detail workflows, but it cannot be surfaced directly as Summary text.
- Summary candidates that still contain structured evidence markers are rejected before being stored as company-specific prose.

## Validation

- Added ScoutBox 0.11.52 targeted regressions for evidence-marker detection, stale-summary repair, structured-section filtering, and the no-raw-evidence list rendering rule.
- Python AST parse and compileall.
- Statistics and toolbar JavaScript syntax checks.
- Docker Compose YAML parse.
- Shell syntax checks.
