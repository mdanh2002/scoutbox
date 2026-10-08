# ScoutBox 0.10.33

## Discovery acquisition is additive

Direct source acquisition no longer suppresses search-engine discovery. For every selected direct-capable source, ScoutBox performs at least one parallel `site:` search using an eligible search provider even when the direct adapter succeeds and returns many records. This applies to both Local AI Discovery and Cloud Web. Cloud Web qualifies those supplemental search-engine records with Cloud AI before persistence.

The normal capability preference remains:

**official unrestricted API → official credentialed API → official feed/RSS → deterministic direct-page adapter → search-engine discovery**

Search-engine discovery is a parallel coverage path rather than a conditional last resort.

## Discovery telemetry

- Dashboard Search Activity counts direct-source network requests in addition to ordinary search-provider query requests.
- Direct adapter returned-item counts are recorded in `SearchProviderStat.results` without counting cache reads as additional network requests.
- Direct network/parser failures contribute to the existing error telemetry.
- **Search Provider Performance** is renamed **Discovery Performance**.
- **Search Provider Activity** is renamed **Discovery Source Activity**.
- Excel export filenames and source/result column labels use the new terminology.

## Source catalog and adapters

- **Hacker News Who is Hiring** moved to **Developer / engineering communities**; the one-item Fresh job feeds / communities category is removed.
- **Lobsters** gains a job-tag RSS adapter.
- **DEV Community Hiring** uses the public DEV/Forem article API with hiring-tag filtering.
- **Indie Hackers Jobs** gains a deterministic direct-page adapter.
- **Wellfound** gains a deterministic direct-page adapter.
- **LinkedIn Jobs** gains a credential-gated Job Library adapter. The Job Library is supplemental and does not represent all LinkedIn Jobs inventory.
- **Glassdoor** gains an explicitly enabled, credential-gated Jobs API adapter and stores an attribution flag for displayed API-derived opportunities.
- **Indeed** is labelled partner-only for direct search; ordinary search-engine discovery remains available.
- **ZipRecruiter, Dice and Monster** remain search-engine discovery targets rather than being mislabelled as general direct-search APIs.

## Address Book and Recent Activity

- The Address Book source hyperlink is now rendered in the **Summary** cell immediately after the final summary word with a small left gap.
- The Contact-cell source icon and old email-domain Summary icon are removed, leaving one source hyperlink per row.
- Fit remains a separate right-side control and cannot collide with the inline source link.
- Dashboard Recent Activity groups automatic Address Book promotion bursts by source and 15-minute window. The full Audit Log retains every original event.

## About ScoutBox

- Removed the **Status, logs and recovery** subsection.
- **Common data checks** no longer uses the nested bordered-box treatment and remains available as a flat troubleshooting subsection.

## Configuration

`.env.example` documents optional LinkedIn Job Library and Glassdoor partner variables. Glassdoor direct API execution is disabled unless `GLASSDOOR_API_ENABLED=1` and the required partner credentials are present. Missing optional direct credentials never disable the parallel search-engine path.

## Upgrade

Migration `0087_v01033_discovery_performance_sources` updates source categories and capability metadata and creates the additional developer-community source presets. It does not add schema columns.

Routine future releases increment the patch component unless a minor/major version change is intentionally chosen. For routine releases, increment only the patch component.
