# ScoutBox 0.8.107

## Resource Usage range consistency

- The Cloud Usage card now follows the Resource Usage period selected at the top instead of always showing only the current day's counters.
- Week, Month, All, and custom date ranges aggregate the retained daily Cloud AI safety counters for the selected calendar-day buckets. The card heading changes with the active range.
- Because Cloud AI hard limits are enforced and stored per local day, multi-day gauges compare the selected usage with the current configured daily limit multiplied by the number of selected calendar days. The card explains this directly; daily enforcement behavior is unchanged.
- The live Resource Usage refresh uses the same period-aware Cloud Usage calculation as the initial page render.
- Custom-range context is preserved when drilling into the Errors usage list.
- The existing CPU, RAM & Tokens chart behavior is intentionally unchanged.

## Address Book company-enrichment stale jobs

- Address Book company-research workers now treat a contact that was deleted, recycled, purged, or otherwise disappeared after queueing as a normal stale job. The job completes as skipped before it waits for Local Discovery or starts research.
- This prevents the local Django `Contact matching query does not exist.` exception from appearing as a failed `company_enrichment` AI Request when no AI inference actually ran.
- Migration `0067_v08107_resource_usage_stale_contact_cleanup` converts matching historical stale Address Book research failures to completed/skipped jobs and removes only their placeholder AI Request rows. Real provider/model AI Request logs are not removed.
