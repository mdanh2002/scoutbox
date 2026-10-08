# ScoutBox 0.9.40

## Opportunity list — Remote column

Long Remote classification captions no longer stay on a single line and push the Remote column wider. The caption can wrap naturally and is clamped to at most two visible lines inside a bounded Remote column.

The presentation helper now allows up to 60 characters for the display label instead of pre-cutting it at 32 characters. Existing hover text still carries the classification confidence and reason, so the compact list remains readable without discarding the underlying explanation.

## Compatibility

This is a presentation-only change. No database migration, discovery behavior, AI routing, timeout setting, or blacklist behavior changes in 0.9.40. The 0.9.39 UI fixes are retained.
