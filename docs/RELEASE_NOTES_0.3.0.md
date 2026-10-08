# v0.3.0 release notes

This release keeps the v0.2.0 CV-first discovery pipeline and UI, and changes historical-application interpretation/ranking controls.

## AI-first arbitrary-layout application import

- XLSX, CSV, DOCX, TXT and PDF no longer require a fixed column/field format.
- The new `import_inference` AI stage interprets arbitrary sheets, tables, prose and notes.
- Missing fields are explicitly left blank instead of guessed.
- Company is treated as the primary duplicate/history anchor.
- Notes and explicit outcome/status remain dedicated fields.
- Proposed rows show AI vs deterministic fallback inference and require confirmation.
- Exact application dates are only stored when the source provides an exact date.

## Same-company cooldown

- Exact previously applied roles remain suppressed.
- Different roles at a recently applied company remain visible but rank down.
- Defaults: 90-day company cooldown, 20-point recent-company fit penalty, 8-point caution when the historical application date is unknown.
- These settings are editable under System Configuration.

## Per-stage token caps

- AI Configuration now stores max input/output token caps for every production pipeline stage.
- Sensible defaults are supplied for filtering, enrichment, summarization, CV/email/ATS generation, cold-contact drafting and import inference.
- Caps are enforced across Ollama/OpenAI/Gemini paths; input preflight is provider-neutral and output caps are passed to provider APIs where supported.
- Restoring token defaults preserves provider/model choices.
- Performance Lab remains independent of production token routing.
