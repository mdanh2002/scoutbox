# ScoutBox 0.10.105

## Focus upgrade stability

- Supersedes queued, running and stale pre-0.10.104 Focus rebuild jobs during upgrade.
- Preserves established Focus labels instead of clearing them when Local AI times out.
- Leaves unclassified records retryable and relies on bounded backfill/recovery rather than full taxonomy churn.

## Job-board employer and role integrity

- Adds Workopolis and GulfTalent to the shared job-board/platform registry.
- A job-board host can no longer become the employer when the listing page identifies another company.
- Employer recovery accepts explicit listing evidence such as `Binance.US seeks...` and repairs existing platform-as-company rows on upgrade.
- Replacement role validation now uses the fetched replacement page title and employer evidence, not the stored row title.
- Incidental product/technology mentions in a JD are no longer sufficient employer corroboration.
- Job-board UI fragments such as `Cover Letter Assistant About this role` are removed from role titles; existing affected records are repaired during upgrade where page text contains a better role title.

## Campaign Template recycle lifecycle

- Campaign Templates now have `deleted_at` and single/bulk deletes move them to Recycle Bin instead of permanently deleting them.
- Recycle Bin now includes Campaign Template type filtering, restore, permanent delete, empty-bin handling, counts and diagnostic export IDs.
- Deleted templates are excluded from new-campaign template selection and normal template payloads.
- Campaign Templates toolbar adds a Show Deleted icon immediately after Delete.

## UI and diagnostics

- Dashboard Discovery Activity and Resource Usage now support a 14-day range.
- Hidden Lead notes derived from unsuitable opportunities are shortened to a generic retention note.
