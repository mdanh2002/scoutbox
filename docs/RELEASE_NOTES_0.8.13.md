# ScoutBox 0.8.13 release notes

## Dashboard and navigation

- Removes the misleading idle-task sentence beneath active ScoutBox activity.
- Removes the duplicate Discovery Activity last-updated label; the global header clock remains authoritative.
- Adds spacing above the next scheduled campaign line and replaces the boxed Diagnostics refresh control with a larger unboxed glyph.
- Embeds the sidebar ScoutBox logo directly in the base document and stabilizes its render slot to prevent flicker during rapid navigation.

## Search provider status

- Search Source provider health glyphs no longer have circular/square containers.
- Uses new icon names and shapes for configured-but-unused, no-results, healthy, warning and error states so stale browser assets cannot preserve the old appearance.

## Resource Usage and Statistics

- Adds breathing room above CPU/Memory/GPU and fixes Input Tokens metric alignment.
- Removes redundant Input Token Purposes explanatory copy and moves its table immediately beside the donut chart.
- Adds top margin above the Statistics funnel/KPI row.

## Opportunities and Market Studies

- Removes Source from the Opportunities main list.
- Raw Text now strips repeated blank lines and merges short crawler-wrapped fragments where safe while preserving bold and links.
- Market Studies filters GitHub, Bitbucket, GitLab, Medium and other generic publishing/code/job/social platforms and de-duplicates companies.
- A cleanup migration removes existing general-platform/duplicate Market Studies rows.

## Performance Lab

- In-progress PerformanceRun placeholders are hidden from Recent Runs until the background job has completed, preventing transient Failed status before a successful DOCX→PDF result appears.
