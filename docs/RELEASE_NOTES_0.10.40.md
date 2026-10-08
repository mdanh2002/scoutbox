# ScoutBox 0.10.40 release notes

ScoutBox 0.10.40 focuses on bounded Local discovery expansion, stronger page/content interpretation, cleaner list presentation, safer URL-health behavior, and more useful campaign statistics.

## Discovery and content quality

- Local AI Discovery can follow relevant links found in downloaded HTML with configurable **Follow-up pages / run** (default 50) and **Follow-up link depth** (default 3, maximum 5). The feature is disabled for Cloud Web Discovery.
- Follow-up traversal deduplicates canonical URLs, blocks obvious navigation/legal/social noise, keeps arbitrary cross-domain traversal constrained, and recognizes common ATS domains.
- The existing company-first career/project/collaboration search remains the primary path and the new follow-up frontier extends it rather than creating a second unbounded crawler.
- HTML-to-text extraction preserves table rows, definition labels/values, headings, paragraphs and list items before Local AI analysis.
- Facebook Pages to Watch now requires stronger direct Page-owned hiring/career evidence, cleans contaminated result titles, retains temporary validation failures, and periodically revalidates a bounded number of stale watches.

## Opportunities, Leads and Address Book

- Opportunity list summaries retain useful technical context with a 50-word maximum; Address Book list summaries are now similarly concise while the full stored company summary remains available.
- Legacy Opportunity titles are retrospectively cleaned of decorative Unicode and embedded compensation fragments. Recoverable title salary evidence is moved to salary fields instead of being discarded.
- Salary provenance from the job post is shown as a tooltip rather than visible `Job post` text.
- The Opportunity list no longer uses a separate Apply Via column or Apply Now badge. A compact apply-method icon sits beside the role/company information; applied roles use a more prominent state and applied tooltip/date.
- Manual re-evaluation progress for Opportunities, Hidden Leads and Address Book uses one processed/selected calculation for the count, bar and percentage.

## URL health

- Opportunity HTTP-200 soft-404 checks remain job-aware (applications closed, role missing/expired and similar signals).
- Hidden Lead and Address Book URLs use only page-unavailable semantics; a company/contact/project page is not treated as bad simply because no career content is present.
- A later transient HTTP 403/429 no longer overwrites a previously successful displayed status. First checks still show 403/429, and retry information is retained for diagnostics.

## Statistics and activity

- Campaign Statistics adds **Address Book Entries Found** and **Number of Requests** charts. Request counts distinguish Local discovery traffic (search engine/direct/follow-up) from Cloud AI.
- Local and Cloud Token Usage charts include visible Input, Output and Reasoning legends.
- Dashboard Recent Activity consolidates Address Book promotion batches while leaving the underlying audit rows unchanged.

## Upgrade

Migration `0091_v01040_local_followup` adds the Local follow-up limits. An idle-aware 0.10.40 startup backfill performs retrospective data normalization without repeatedly rewriting records after its completion marker is saved.

Routine future releases increment the patch component of the 0.10.x line; see `RELEASE_POLICY.md`.
