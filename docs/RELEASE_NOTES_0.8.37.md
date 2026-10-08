# ScoutBox 0.8.37 release notes

Released on 2026-08-21 00:47:00.

## AI & Discovery diagnostics

- Test Model now writes partial stage/attempt results to its BackgroundJob as testing proceeds instead of only saving a result at the end.
- Returning to AI & Discovery while a model test is running restores completed-stage status and resumes polling the active job automatically.
- Stage question marks update as each stage completes; Primary and Fallback routes have separate borderless status indicators so a failed fallback no longer makes a working primary look like a failed stage.
- A stage is considered usable when at least one configured execution route works. Failed secondary routes remain visible as route warnings in the detailed results.
- Tested stage names remain clickable and open the stored stage result, provider/model target, individual attempts, and exact failure text.
- While Test Model or Test Discovery is active, the Discovery action-row buttons are disabled to prevent configuration changes or overlapping tests.
- Test Discovery progress also resumes after returning to the page. The server reuses an already-active same-type test and prevents conflicting Discovery diagnostics from running concurrently.
- The Test Discovery dialog and Model Test Results dialog are wider; diagnostic tables wrap long details rather than forcing horizontal scrollbars.
- Source-Guided URL Discovery probes up to three enabled search engines and passes when any provider produces parsed results. Each provider's result/failure remains visible.

## Campaign timing

- New CampaignRun rows store worker-side monotonic `run_duration_seconds` on completion, stop, or failure.
- Last Run Duration prefers this runtime measurement and falls back to `started_at`/`finished_at` for historical runs. Legacy zero values cannot hide a non-zero timestamp duration.
- Short runtimes keep minute precision instead of displaying a misleading `0.0 min`.

## Notifications

- Recent Hidden Lead items now link to `Hidden Leads?lead=<id>` and automatically open the selected lead detail modal on arrival.
- Hidden Leads notification deep-links pin the requested active lead onto the first rendered page before opening its detail modal, so pagination/list cleanup cannot strand the user on the generic list.
- The scheduled-search status line in the top-right notification popover now has more internal spacing, a slightly wider popover, and wrapping so long timestamps stay inside the border.

## Opportunity detail

- Company Info confidence is presented as a compact confidence icon next to the heading, with the confidence meter/percentage in the right-side heading actions.
- The `Refreshing…` company-research indicator is smaller and less visually dominant.
- Company Info and Extracted Facts action icons have additional edge spacing.
- Extracted Facts now includes an inline collapsible Raw data section while retaining the existing raw-data popup action.

## Hidden Leads list

- The Company column is narrower to leave more room for Summary. Long company names can wrap to a second line instead of forcing the column wider.

## Compatibility

- All ScoutBox 0.8.36 behavior remains included.
- No new database migration is required for 0.8.37.
