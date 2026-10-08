# ScoutBox 0.10.41 release notes

ScoutBox 0.10.41 completes the post-0.10.40 corrections around retained discovery data, location accuracy, list readability, URL-health semantics and diagnostic usability.

## Discovery and Facebook Pages

- Facebook Pages to Watch applies deterministic junk rejection before relying on a direct Facebook fetch, so clearly unrelated retained pages can be removed even when Facebook blocks automated validation.
- Indexed Page evidence is validated more strictly and contaminated browser/search-engine title suffixes are cleaned before storage.
- Existing Page rows are revalidated by the one-time upgrade repair; temporary unavailability remains distinct from confirmed relevance or irrelevance.

## AI input and Opportunity quality

- Structure-aware visible-text extraction is shared across Local discovery, enrichment and manual re-evaluation paths. Tables, headings, lists and common label/value layouts retain useful adjacency for smaller local models.
- Opportunity summaries use natural technical synopses of roughly 25–40 words, with a hard 50-word maximum, rather than terse `role: keyword` or `technical focus` patterns.
- Runtime Cloud and Local discovery serialization now preserves the full 600-character summary allowance used by the Opportunity model.
- Opportunity re-evaluation can refresh the role-specific location and canonical role country independently from company/HQ location. Explicit JobPosting/Job Location/Location requirements/“role is based in” evidence outranks company offices, candidate operating locations and related-job content.

## Address Book and URL health

- Address Book list summaries are shortened without discarding the full stored company summary.
- Existing Address Book records missing Fit are assessed/backfilled from retained evidence where possible. A genuine score of zero is retained as an assessment; missing assessments remain visibly distinct.
- Opportunity HTTP-200 soft-404 checks remain job-aware. Hidden Leads and Address Book use page-unavailability semantics only, and legacy inappropriate job-presence warnings are cleared by the upgrade repair.

## UI and diagnostics

- Re-evaluation count, progress bar and percentage share one progress calculation so the displayed fraction and percentage do not drift.
- Campaign Details → Query Rotation supports 10/25/50/100 rows per page, defaulting to 10, including dynamically regenerated previews.
- Diagnostic ZIP and JSON filenames include the selected export scope, effective date range and a millisecond timestamp to avoid ambiguous or cached repeated downloads.

## Upgrade

Migration `0092_v01041_role_location` stores role-specific location data and Facebook Page validation state. The idle-aware 0.10.41 startup repair normalizes retained Opportunity summaries/location metadata, backfills missing Address Book Fit where possible, removes legacy inappropriate URL-content warnings, and revalidates Facebook Pages to Watch.

Routine future releases increment the patch component of the 0.10.x line; see `RELEASE_POLICY.md`.
