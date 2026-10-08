# ScoutBox 0.8.90

0.8.90 is a focused maintenance release on top of 0.8.89.

- Rebuilds **About ScoutBox → Overall System Architecture** as one contained diagram combining the product flow and runtime stack. Django/Gunicorn, PostgreSQL, Redis, Celery Beat/Worker, Cloud AI/Ollama, search/page retrieval, mail, storage and diagnostics are visible in the diagram, with concise two-column notes below.
- Fixes **Dashboard → Recent Campaigns → First / Last** so the time range is rendered as ordinary full table-cell content rather than an inline timestamp element that exposed a dark remainder inside the cell.
- Makes **Poor Fit with low or unavailable confidence** display as a literal `?`. New local Fit classification results also persist an explicit fit-confidence value.
- Adds **Maintenance → Rebuild Missing AI Data**, shown only when **AI & Discovery → Discovery Method = Cloud Web**. The violet action runs in the background, supports Today / 3 / 7 / 30 days / All time, and attempts only fields currently displayed as unknown for Company Info, Remote Status, Post Age and Fit. Existing populated values and workflow state are preserved.
- Fixes **CPU, RAM & Tokens** hover sampling so the selected timestamp follows the current horizontal pointer position and the dashed guide is drawn at the corresponding sample, including when the canvas is responsively scaled. The live chart continues to refresh every 15 seconds.

No database migration is required for this release.
