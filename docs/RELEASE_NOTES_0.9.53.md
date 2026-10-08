# ScoutBox 0.9.53

Released: 2026-08-31

## Opportunity re-filtering

The Opportunities toolbar now includes **Filter Selected**. The action queues a background job that re-runs the configured `first_filter` route against the retained role/company/URL/page-description evidence for each selected row.

The filter deliberately does not recalculate `fit_score`, remote status, freshness, salary, company research, or application state. It is intended to correct persisted false positives such as editorial pages, documentation, generic job-board/directory pages, company-only hiring signals, and clearly irrelevant rows.

Automatic recycling is conservative. A row is recycled only when the model returns a high-confidence rejection. Ambiguous results stay visible as `review`. Any Opportunity with Application history, an application draft request, or active application-preparation work is protected from automatic recycling even when the filter rejects it.

Progress is visible both above the Opportunities list and in Dashboard running work. Completion reports checked, kept, recycled, protected, review, failed, and unprocessed counts. Each checked Opportunity retains the most recent manual filter decision in `extracted_facts.manual_opportunity_filter`.

The action uses the current AI & Discovery `first_filter` provider/model. It operates only on evidence already retained by ScoutBox and does not initiate another web search.

## Migration

`0078_v0953_opportunity_filter_job_kind` adds the `Opportunity filter` display choice for `BackgroundJob.kind`. No database column or Opportunity schema is changed.
