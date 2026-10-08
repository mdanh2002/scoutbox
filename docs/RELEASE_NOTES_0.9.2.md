# ScoutBox 0.9.2

## Dashboard chart axis

- Discovery Activity labels are generated from machine-readable bucket timestamps rather than displaying long preformatted strings directly.
- Last 24 hours uses time labels.
- Last 3 days uses two compact lines: date and time.
- Week uses weekday/date, Month uses date, and Year uses month/year.
- Tick count is kept compact and first/last labels are anchored inward to avoid SVG clipping.

## Resource Usage width containment

- Fixes a 0.9.1 flex-layout regression where the chart column used `width:100%` while the current-values panel remained beside it.
- The chart column now uses `flex: 1 1 0`, `width:auto`, `min-width:0`, and inline-size containment while side-by-side.
- When the layout stacks at laptop widths, the chart returns to 100% width.
- Existing full-range sample aggregation and live-point merge behavior are unchanged.

## AI timeout copy

- Shortens the Miscellaneous timeout explanation to: “Per-attempt AI timeouts. Chatbot uses its own timeout; non-AI service timeouts are unchanged.”

## Campaign linkage repair

- Fixes Hidden Lead → Opportunity/Application promotion paths that did not copy the lead's campaign relation.
- Opportunity and Hidden Lead detail pages self-repair a missing relation when exact campaign provenance is already stored.
- Existing attributable rows are backfilled first from exact `CampaignRun.result` Opportunity/Lead IDs, then from `extracted_facts.campaign_id`, `market_study_lead_id`, and Hidden Lead `ai_state._usage.campaign_id`.
- Rows with no exact campaign provenance remain `Direct / manual`; ScoutBox does not infer a campaign from company/title similarity.

## Schema

Adds data migration `0073_v092_campaign_linkage_repair` to restore missing campaign M2M rows from exact stored provenance. No schema fields are added or changed.
