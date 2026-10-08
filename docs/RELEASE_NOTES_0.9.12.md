# ScoutBox 0.9.12

## Fixed

- Hidden Leads Excel export now downloads normally instead of being swallowed by asynchronous pagination.
- The shared server-pager handler now intercepts only actual pagination/sort links and explicitly leaves export/download links to the browser.
- This also repairs the same latent issue for Search Activity, AI Requests XLSX/JSONL, Audit Trail, and Recycle Bin exports.
- Audited the remaining list-view export/download controls; standalone/client-paginated exports are not routed through the asynchronous server-pager handler and require no behavior change.

No database migration is required.
