# ScoutBox 0.9.54

## Compact bulk-action toolbar

Opportunities now show icon-only Filter and Delete actions. Hidden Leads now show icon-only Filter, Blacklist and Delete actions. Every control has a descriptive title/ARIA label so the meaning remains clear without consuming toolbar width.

## Hidden Leads selected filter

Selected Hidden Leads can be re-checked using the configured `first_filter` AI route and the evidence already retained by ScoutBox. The filter does not run another web search and does not recalculate fit score or other enrichment fields.

The filter keeps plausible company outreach/hiring signals, recycles only high-confidence noise or clearly irrelevant leads, and leaves concrete jobs/contracts or uncertain cases for human review. Existing application/outreach history and active preparation protect a lead from automatic recycling.

The task runs in the background with progress displayed above Hidden Leads and on Dashboard. The latest decision is stored in `CompanyLead.ai_state.manual_hidden_lead_filter`.

## Recycle Bin action distinction

Permanent deletion of selected items remains a red trash-can action. Emptying the entire Recycle Bin now uses a distinct sweep/broom icon and purple background so the two destructive actions are not visually confusable.

## Database

Migration `0079_v0954_hidden_lead_filter_job_kind` adds the `Hidden Lead filter` display choice for `BackgroundJob.kind`. No Opportunity or Hidden Lead data columns are added.
