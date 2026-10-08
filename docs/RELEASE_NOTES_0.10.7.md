# ScoutBox 0.10.7

## Filter result history dialog

The latest manual filter result on Opportunities and Hidden Leads now opens in a modal instead of using an inline expand/collapse panel. The dialog retains the last 10 runs for that dataset, with a compact history selector and a full per-entry result table for the selected run.

Provider and model are shown prominently for every run. Historical jobs that predate provider/model persistence are clearly labeled as legacy rather than rendering an empty route.

The compact summary focuses on the outcomes that matter after execution: kept, recycled, and surviving entries with Fit >=75. A result row counts as a surviving strong fit only when `fit_after >= 75` and the decision is not `recycled` or `failed`.

When a background-job wrapper reaches a failed terminal state after producing usable filter results, the completion notification now reports those persisted results instead of replacing them with a generic failed message. Truly empty failed runs still report the terminal error.

No database migration is required.

Routine future releases increment the patch component on the 0.10.x line unless a release is deliberately designated as major.
