# ScoutBox 0.10.101 release notes

## Focus classification

- Adds a persistent `Focus` facet to Opportunities, Hidden Leads, and Address Book.
- New records are classified from actual record evidence with Campaign provenance used only as a weak hint.
- Runtime classification compares against a bounded representative sample of records from the same list type. Config → General exposes `Focus comparison records` (default 100) and `Maximum focus groups` (default 15); internal maintenance may operate within an approximately ±20% band around those targets.
- Migration `0121_v010101_focus_facets` performs a one-time full backfill of every existing Opportunity, Hidden Lead, and Address Book record. This upgrade backfill deliberately does **not** use the runtime comparison-record limit.
- Gradual maintenance merges compatible low-volume Focus groups when the active taxonomy grows beyond its configured operating range. No automatic Cloud AI is used for Focus assignment or maintenance.

## List controls

- Opportunities replace the non-visible Status facet with a searchable Focus facet.
- Hidden Leads and Address Book gain searchable Focus facets after Country.
- Existing Search fields on those three lists are shortened to make room; no new list-search fields are introduced.
- Opportunities and Hidden Leads move action controls to the right edge of the toolbar. Blacklist, Address Book, and Applications & Outreach keep their existing action placement.
- Address Book's New/Seen facet now uses `All items` as its unfiltered label.
- Focus is included in the corresponding exports.

## UI wording and Post Age

- Best Fit/reset helper messages are reduced to neutral guidance such as `Review selections, then click Apply.`
- Fresh records display `< 1 week` instead of `0 days`/the first one-week bucket.
- Post Age hover details use concise multiline `Evidence:` wording and normal font weight.

## Tooltip placement

- Structured list tooltips now render in a fixed body-level overlay with viewport-aware above/below placement. A tooltip on the last rows no longer expands or distorts the table/list area or pager.

## QA

- Adds targeted 0.10.101 static regression checks and Django regression coverage for Focus classification/configuration, the one-time unrestricted upgrade backfill contract, toolbar/facet changes, Post Age wording, and viewport-level tooltip rendering.
