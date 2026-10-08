# ScoutBox 0.10.39 release notes

ScoutBox 0.10.39 is a full-package corrective release for discovery quality, telemetry provenance, location accuracy, list-view consistency, diagnostic exports, and UI feedback.

## Changes

- Opportunity list summaries are restored to useful natural technical synopses, normally 15–35 words and never more than 50 words. The upgrade backfill retrospectively rebuilds historical summaries from retained job evidence.
- Search Activity now presents generic direct HTTP work as **Direct Search**, removes redundant `Direct ·` prefixes from query text, keeps direct URLs clickable, and uses parsed adapter-result telemetry so successful direct sources no longer appear to return zero results.
- Opportunity, Hidden Lead, and Address Book source charts report acquisition provenance — Search engine, Direct search, or Cloud AI — rather than Local GPU/model execution. Empty cloud metadata can no longer classify every record as Cloud AI.
- Role-country inference now prioritizes JobPosting structured location, labelled role-location fields, location requirements, and US city/state evidence. Arbitrary footer/navigation country mentions and URL TLDs are not used as role-country evidence for Opportunities. This fixes cases such as a San Francisco vacancy being stored as Singapore.
- Missing/placeholder country values are hidden in Opportunity, Hidden Lead, and Address Book rows. Country and status facet totals are derived from their displayed options, and similar list-view facet totals are normalized to the same invariant.
- Latest re-evaluation cards use a working text **Close** link to the left of History. Best Fit and Reset confirmations stay in a stable message area above Apply Via without disturbing button order.
- About ScoutBox uses distinct Main workflow/Discovery Mode icons. Internal ScoutBox links in the About Word export become bold labels rather than localhost URL arrays.
- Navigation attention badges retain automatic refresh on page load, every 60 seconds, tab visibility return, and pageshow.
- Export Diagnostic Data now lets the user independently select **ScoutBox Data & Records** and **Operational Logs & Diagnostics**. At least one selection is required, both are unchecked initially, and **Time period** replaces the old Recent data wording without the verbose helper sentence. Diagnostics-only exports omit the retained candidate/job/contact corpus while keeping operational telemetry and configuration useful for debugging.
- Existing discovery cleanup is retained: direct Facebook Page validation, semantic soft-404 detection (including closed applications), exact employer/ATS role recovery, explicit post-date parsing, country-restricted remote handling, mixed-script title cleanup, Company career pages help text, and Local/Cloud discovery-mode separation.

## Upgrade

Keep your existing `.env` and Docker volumes, replace the application files with this package, then run:

```bash
./restart_scout_box.sh
```

No new schema migration is required beyond the migrations already included in the full package. The 0.10.39 startup backfill is idle-aware and records its completion marker so it does not continually rewrite historical rows.

Routine future releases increment the patch component unless a minor or major version change is intentionally warranted.
