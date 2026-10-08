# ScoutBox 0.9.18

## About ScoutBox reference layout

- Removes the small **Read-first reference** badge from Database Info; the safety/read-only guidance remains in the explanatory copy.
- Reorganizes **Troubleshooting Tips** into full-width sections.
- **Status, logs and recovery** uses a two-column command grid and adds checks for `discovery_worker`, Celery worker ping, active tasks and reserved tasks.
- **Common data checks and credentials** moves below into its own full-width section. Long Docker/Django shell commands stay on one line inside horizontally scrollable command fields rather than wrapping excessively.
- Adds read-only examples for active Background Jobs, Campaign Runs, AI warnings/failures and Recycle Bin record counts, plus a clearly marked local credential-recovery command.
- Keeps **Useful scripts & key files** as a separate full-width reference.

## AI Requests toolbar

- Moves the filtered AI request count to the top-right of the primary filter toolbar.
- Moves Range / From / To / Apply to the bottom-center toolbar, on the same row as Rows/Export and page navigation at normal desktop widths.
- Search/runtime/provider/task/status filtering keeps the current date range through hidden fields; applying a date range preserves the other active filters and sort order.

No database migration is introduced in 0.9.18.
