# ScoutBox 0.11.29

## Fixed

- Automatic Hidden Lead reassessment now runs through a low-priority Local AI maintenance lane so it yields to campaign discovery and other primary work instead of saturating Ollama/GPU capacity.
- Automatic Hidden Lead reassessment disables fallback AI retries for the maintenance pass, preventing a bad/slow lead from triggering extra local model churn.
- Busy or timed-out automatic Hidden Lead reassessment items are recorded as review/timeout outcomes and the pass continues, instead of hanging indefinitely on the current lead.
- Hidden Lead reassessment progress is written from the durable reassessment pass snapshot rather than stale BackgroundJob percentages, preventing visible progress from jumping backwards.
- Re-evaluation history popups hide completed zero-record placeholder runs while keeping current runs, past runs with result entries, and runs with real errors.
- Campaign and Campaign Template Show Deleted buttons now use the same toolbar icon footprint as the neighboring Delete/Add actions.

## Changed

- Opportunity Campaign/Country/Focus filters are searchable multi-select dropdowns with Select/Deselect all controls.
- Hidden Lead Campaign/Country/Focus filters are searchable multi-select dropdowns with Select/Deselect all controls.
- Address Book Country/Focus filters are searchable multi-select dropdowns with Select/Deselect all controls.
- Re-evaluation history modal subtitles now describe the current run plus meaningful past result runs instead of showing raw stored-run counts.

## Notes

No database schema migration is required.
