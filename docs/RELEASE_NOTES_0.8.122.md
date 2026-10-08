# ScoutBox 0.8.122

This UI maintenance release builds directly on 0.8.121/hotfix1 and changes only the list-control layout for three history pages.

- **AI Requests:** removes the duplicate item count from the top toolbar and removes the explanatory note below the list. Rows-per-page, XLSX export, raw JSONL export, page information and pagination now share one centered footer row.
- **Search Activity:** removes the duplicate item count from the top toolbar. Rows-per-page, XLSX export, page information and pagination now share one centered footer row.
- **Audit Trail:** removes the duplicate item count from the top toolbar. Rows-per-page, XLSX export, page information and pagination now share one centered footer row.
- Footer page-size controls use ScoutBox's existing async page-size mechanism, so changing page size keeps the active search, filters, date range and export parameters intact.
- No database migration is added.
- Discovery, search-provider, resource telemetry and AI-processing logic are unchanged from 0.8.121.
