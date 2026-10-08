# ScoutBox 0.11.51

## Fixed

- Hidden Leads no longer intentionally fall back to reusable taxonomy descriptions such as `Specializes in emulation and virtualization technology.` when the retained evidence does not identify what is specific to that company.
- Hidden Lead summary generation now prefers retained company facts, named offerings, or a concrete evidence-backed company sentence. When there is not enough evidence for a distinguishing description, ScoutBox shows `Summary pending.` instead of inventing a generic description.
- Existing generic or exact-duplicate Hidden Lead summaries are eligible for deterministic repair on the list view, and company research can replace stale generic summaries from retained company facts.
- Corrected the Hidden Leads summary refinement path so an unrelated stale MiniBrowser deadline fragment can no longer interrupt summary generation. The same stale fragment was removed from outreach draft generation.
- Normalized inactive Show/Hide Deleted toolbar button borders and icon weight across list views while preserving the intentional active state when deleted records are shown.
- Icon-backed Mark As/read-state selectors now release stale mouse focus when their native menu is dismissed by clicking elsewhere or pressing Escape; normal keyboard focus remains available.
- Campaign Templates now keeps Search and its action toolbar outside the bordered list shell. The list/table and bottom Rows/Export/pagination bar remain inside the border.
- Long single Focus selections reserve spacing before the dropdown caret, so the arrow remains visible instead of being covered by the selected focus text.

## Validation

- Added ScoutBox 0.11.51 targeted regressions for Hidden Leads summary specificity, legacy duplicate repair, shared toolbar states, Campaign Templates list-shell structure, and Focus caret spacing.
- Python AST parse and compileall.
- Statistics JavaScript syntax check plus the new toolbar focus-release JavaScript syntax check.
- Docker Compose YAML parse.
- Shell syntax checks.
