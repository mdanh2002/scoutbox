# ScoutBox 0.11.130

## Candidate Profile Resume actions

- Removed the inline explanatory sentence following **Autopopulate Candidate Profile**.
- Added a dedicated blue-teal action treatment so Autopopulate is visually closer to the adjacent primary **Auto-create Campaign Templates** action without making both buttons identical.
- Kept the existing background-job, progress, cancellation, aggregation, de-duplication, and 160 / 80 vocabulary-limit behavior unchanged.

## Confirmation dialogs

- Gave the shared two-action confirmation dialog an explicit compact responsive width.
- Applied the same compact treatment to custom simple binary confirmations for document deletion, Auto-create Campaign Templates, blacklist reset, and Empty Recycle Bin.
- Shortened the Candidate Profile autopopulate confirmation copy while retaining the warning that current Resume concepts/likely roles are replaced and unsaved Candidate Profile edits should be saved first.
- Left re-evaluation dialogs and dialogs containing selectable options or multi-field workflows unchanged.

## Compatibility

- No database schema or Candidate Profile data transformation is required.
- Existing 0.11.129 Candidate Profile autopopulation and 0.11.128 Resume-grounded re-evaluation/diagnostics behavior remain intact.
