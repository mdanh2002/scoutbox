# ScoutBox 0.11.131

## Candidate Profile document tables

- Narrowed the Cover Letter **File** column to align its right edge with the Resume **File** column.
- Expanded Cover Letter **Added** so it spans the same horizontal region as Resume **Added** plus **Campaign Template Generated**.
- Let the remaining action column occupy the right side of the table while retaining right-aligned **Delete**.
- Added ellipsis handling for long Cover Letter labels so filenames do not disturb the fixed table geometry.
- Matched the Cover Letters table minimum width to the Resumes table for consistent alignment on narrow screens.

## Compatibility

- No database schema or data migration is required.
- Candidate Profile autopopulation, campaign-template generation, confirmation dialogs, discovery, re-evaluation, and diagnostics are unchanged.
