# ScoutBox 0.8.40 release notes

Released on 2026-08-21 08:53:00.

## Opportunities and Hidden Leads

- Adds a searchable **Campaign** filter to both standalone lists. It sits before the normal status/read filter and each option shows the campaign's current matching-item count, for example `Technical Writing (40)`.
- Opportunity detail shows the associated campaign name(s) beside the Country summary box, with links to Campaign Detail.
- Hidden Lead detail shows its campaign name(s) directly below Target URL.
- Hidden Leads moves the Rows selector from the sticky top toolbar to the bottom-left list footer beside the item/page count.
- Adds **Add to Blacklist** immediately to the right of Delete Selected. The action requires selection and confirmation, blacklists each usable selected source domain, and removes the corresponding Hidden Lead.

## Campaign detail and navigation

- Adds two historical bar charts immediately below Run History: **Opportunities Found** and **Leads Found**.
- Charts can be grouped by Day, Week, or Month and filtered by a From/To date range. Historical counts are derived from CampaignRun results, so they remain aligned with Run History even if an item is later recycled or permanently removed.
- The Campaigns navigation badge shows enabled/total campaigns as `(running/total)` style state, for example `(4/5)`, with a tooltip explaining the count.
- Opportunity, Hidden Leads, Recycle Bin, and Applications & Outreach count badges expose concise hover explanations.
- Applications & Outreach now has its own unread-count badge.

## AI Requests

- Adds a final sortable **Status** column after Attachments.
- Status is a borderless icon: green check for success and red cross for failure.
- A request is considered failed in this view whenever output tokens are zero, even when the provider's original request flag is otherwise successful.
- XLSX export uses the same success/failure rule.

## List navigation and toolbar consistency

- Standardizes list-view pagination to `<<`, `<`, numbered pages with ellipses, `>`, `>>` for first, previous, direct-page, next, and last navigation.
- The same compact page-window logic is used by both browser-paginated tables and server-paginated Opportunities, Hidden Leads, Search Activity, AI Requests, Blacklist, and Recycle Bin lists.
- Applications & Outreach moves its Rows selector to the bottom-left footer beside item/page counts and replaces the top Rows control with a **Type: All / Application / Outreach** filter.
- Long-running/progress/help icons retain their normal pointer rather than switching to the browser's question-mark help cursor; hover tooltips remain available.

## Queue feedback

- `Application preparation` in preparation-queued notices is now a direct link to the Applications & Outreach list.

## Database

- No new database migration is required for 0.8.40.
- Existing `0030_v0838_hidden_lead_company_info.py` remains the latest schema migration.
