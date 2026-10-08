# ScoutBox 0.8.55

## Resource Usage

- Moves the live “Last updated” timestamp into the right side of the Today / Week / Month / All and custom-date filter row.
- Adds the number of distinct calendar days with actual Resource Usage data for the selected duration.
- Counts the union of UsageMetric, SearchProviderStat and ResourceSample dates so All/custom history is not limited by the 14-day ResourceSample retention window.
- Keeps the day count and timestamp synchronized by the existing 15-second live refresh without adding GPU work.
