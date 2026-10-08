# ScoutBox 0.11.53

## Fixed

- Hidden Leads no longer replace a usable source excerpt with `Summary pending.` while a refined company summary is still being prepared.
- Structured extraction labels such as `[QUALIFICATIONS]`, `[APPLICATION]`, and `[PAGE_TITLE]` are now stripped while preserving the readable prose that follows them. For example, `[QUALIFICATIONS] Software defined radio systems often require: ...` is displayed as `Software defined radio systems often require: ...`.
- The Hidden Leads list can temporarily show a compact, label-free evidence excerpt when no refined/company-research summary is available. When asynchronous summary or company research completes, the normal stored company summary replaces that fallback.
- Hidden Lead detail rendering follows the same rule: extraction labels and the legacy `Summary pending.` placeholder are not shown to the user.
- Empty/failed refinement no longer writes `Summary pending.` back to the database. It retains the existing source material (or clears the old placeholder) so readable evidence can remain visible and later refinement can still replace it.
- New summaries arriving from minibrowser admission, Cloud Web discovery, and existing-lead reassessment are sanitized before storage so new bracket-prefixed summaries are not introduced.
- Added an upgrade migration that removes known extraction labels from existing stored Hidden Lead summaries and clears legacy `Summary pending.` values without discarding the text after those labels.

## Validation

- Added ScoutBox 0.11.53 targeted regressions covering the reported `[QUALIFICATIONS]` case, multi-label summaries, no-placeholder rendering, ingestion sanitization, and the upgrade cleanup migration.
- Python AST parse and compileall.
- Statistics and toolbar JavaScript syntax checks.
- Docker Compose YAML parse.
- Shell syntax checks.
