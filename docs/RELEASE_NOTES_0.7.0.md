# v0.7.0 release notes

- Product names remain **ScoutBox** / **Niche Opportunity Intelligence Portal**; branding, chatbot, discovery, mail, AI routing, import, tracking and other workflows are unchanged from v0.6.1.
- Statistics & Funnel now treats **This week / month / quarter / year** as calendar periods rather than rolling approximations; the same period behavior is shared by Usage & Resource Telemetry.
- Adds a week/month/quarter/year performance comparison using the same core metrics: pages scraped, roles found, duplicates, already-applied matches, high-priority roles, prepared applications, newly applied, responded, followed up, interviews/progression, rejected, accepted/engaged, production tokens consumed and data downloaded.
- Adds selected-period SVG trend charts for discovery activity, application funnel movement, AI tokens and downloaded data. Charts are bundled with ScoutBox and need no external JavaScript/CDN.
- Adds metric definitions so the user can see exactly how each chart/KPI is derived. Production resource reporting excludes Performance Lab traffic so benchmarks do not distort real workflow usage.
- Adds Statistics exports for the currently selected period/filter: CSV, XLSX and chart-oriented PDF.
- XLSX exports contain summary, trend data, week/month/quarter/year comparison, metric definitions and native Excel charts.
- PDF exports contain summary metrics, discovery/funnel/resource charts and the week/month/quarter/year comparison table.
- No database migration is required for this release.
