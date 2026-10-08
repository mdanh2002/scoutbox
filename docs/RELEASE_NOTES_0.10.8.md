# ScoutBox 0.10.8

## List Fit and Company Info polish

Opportunity and Hidden Lead list Fit indicators are now two-digit numeric badges. Display bands are poor (red), low (yellow), medium (green), and high (blue); the exact raw 0-100 score remains in the tooltip and remains the sort value. A non-zero single-digit score uses `10` for the compact display footprint, while a raw 100 displays `99`; neither changes stored data.

Company-size display now rejects zero as invalid evidence. Employee sizes at or above 1,000 are displayed conservatively as `1000+` in compact Company Info badges instead of surfacing very large extracted values such as `10,000+`.

## Manual filter UI

Filter-result summaries use `Strong Fit` rather than `Fit >=75`. The history modal keeps the right-hand result pane as the scrolling owner and contains wheel/touch overscroll so the page behind the dialog does not move.

The filter setup dialog now puts the selection count in the title (`Filter 50 Opportunities` / `Filter 50 Hidden Leads`) and removes the redundant selected-count line. Helper copy was shortened while retaining the Internet Search, Fit recalculation, recycle/protection, and approximate request-cost guidance.

No database migration is required.

Routine future releases increment the patch component on the 0.10.x line unless a release is deliberately designated as major.
