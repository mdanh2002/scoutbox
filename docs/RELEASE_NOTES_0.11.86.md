# ScoutBox 0.11.86

## Discovery and search activity

- Refined Discovery Markets layout, language selection, country flags, search-as-you-type market filtering and alphabetic market ordering with Worldwide Remote last.
- Local-language exploration is always applied where useful; English remains the primary discovery language and retained results continue through the normal relevance and quality gates.
- Expanded worldwide job-source coverage, cleaned source category names and alignment, and removed visual-only Direct badges.
- Added per-request region/locale context to Search Activity and Dashboard activity, eliminated empty activity rows, and prevented multi-site query regressions.
- Added region filtering and consistent date-range controls to Search Activity.

## Resource Usage and Statistics

- Added a Market Coverage chart with separate language and market request rings and two-column legends.
- Corrected Resource Usage range plotting so the CPU, RAM and token chart uses the selected time window even when samples exist for only part of it.
- Made large counters compact, changed Downloaded and Disk Usage cards to automatic MB/GB display, and clarified unavailable provider-reported reasoning usage.
- Corrected provider-native web-search accounting when a provider omits its internal query list.
- Simplified Statistics headings and kept the rejection/suppression report out of the interface while retaining backend diagnostics.

## Facebook Pages and Tracking Links

- Promoted Facebook Pages to a first-class Discovery page with New/Seen state, unread badge, evidence text/source link, detected browser title, icon toolbar, pagination, export and Recycle Bin support.
- Moved Tracking Links into Applications & Outreach, added a compact icon toolbar and embedded Add Tracking Link dialog, external-statistics warnings, and consistent list pagination.
- Added soft deletion, Show/Hide Deleted, restore and Recycle Bin support for Tracking Links. Per-row delete controls were removed; deletion is selection-based from the toolbar.

## Audit, diagnostics and interface consistency

- Added version capture to Audit Trail, lifecycle and upgrade events, and removed scheduler-silence noise.
- Converted diagnostic ZIP preparation to a background workflow with a stable-width preparing state and spinner.
- Standardized date-range presets so they populate and apply From/To values, switch to Custom on manual changes and visibly indicate an active filter.
- Improved navigation/footer presentation, provider-name wrapping, accepted-email status color, chart headings, legends, configuration spacing and About copyright presentation.
