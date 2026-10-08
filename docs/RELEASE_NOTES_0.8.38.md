# ScoutBox 0.8.38 release notes

Released on 2026-08-21 01:16:00.

## AI & Discovery diagnostics

- Test Model now stores and displays **Started**, **Ended**, and **Duration** for every pipeline stage and each individual Primary, Fallback, and search-provider attempt.
- Partial results continue to be persisted after each attempt, so leaving and returning to AI & Discovery restores the current progress instead of restarting at question marks.
- While Test Model or Test Discovery is active, ScoutBox disables the Discovery action buttons, the Source-Guided/Cloud-Web selector, every Primary/Fallback model selector, and all input/output token-cap fields. The tested configuration therefore remains stable for the whole run.
- Primary and Fallback remain independently validated. A working Primary with a failed Fallback keeps its own green result while the Fallback independently shows a warning.
- Source-Guided URL Discovery now validates the configured Primary/Fallback model routes as well as probing up to three enabled search engines. At least one search engine must work, and one configured model route must pass, for the overall URL Discovery stage to be green.
- A single blocked search engine does not fail Source-Guided URL Discovery when another tested engine works; each provider result and exact failure remains visible in the stage details.
- The model-test result dialog is wider and its timing/detail table wraps rather than requiring horizontal scrolling.
- Model-test schema versioning invalidates older stored diagnostic results that did not contain the new per-route URL Discovery validation, preventing a stale overall checkmark with blank Primary/Fallback status.

## Campaign timing

- Campaign **Last Run Duration** is now displayed in seconds rather than fractional minutes.
- The value is end-to-end elapsed time from CampaignRun creation/queueing through `finished_at`, so it includes queue wait as well as worker execution. The worker monotonic runtime remains a corroborating/fallback value.
- This definition is intentionally different from GPU-utilization charts: GPU telemetry can include other local-model work and sampling outside one CampaignRun, while Last Run Duration measures the lifecycle of that specific campaign run.

## Hidden Lead Company Info

- Hidden Lead detail popups now include a Company Info section using the same company-research service as Opportunity Company Info.
- Company Info is persisted on each Hidden Lead, including confidence, facts, public sources, research notes and update status.
- The popup provides a transparent refresh icon; active research jobs resume polling when the lead is reopened.
- A new migration adds the `company_intel` JSON field to Hidden Leads.

## Notification and Company Info UI

- Long notification status text such as the next scheduled search now uses a two-column hanging layout: the status dot stays in its own gutter and wrapped lines align with the first line of text.
- Company Info refresh buttons use a transparent background/border in both Opportunity and Hidden Lead Company Info.

## Compatibility

- All ScoutBox 0.8.37 behavior remains included unless explicitly refined above.
- Upgrade applies migration `0030_v0838_hidden_lead_company_info.py`.
