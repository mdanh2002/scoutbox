# ScoutBox 0.11.120

ScoutBox 0.11.120 adds employer-concentration and cross-source vacancy deduplication controls so one prolific company cannot dominate the primary Opportunities list merely because multiple feeds/providers repeatedly surface its roles.

## Cross-source vacancy identity

- Uses the resolved/fetched vacancy destination as the primary URL identity once available.
- Normalizes common tracking/query noise for comparison without rewriting the user-facing URL.
- When Jobicy, Greenhouse, Lever, Ashby, another board, and an employer page resolve to the same vacancy, ScoutBox keeps one primary Opportunity and merges discovery provenance.
- If an existing row points at a job platform and a later duplicate supplies a direct employer URL, the direct employer destination becomes the preferred target while all original URLs remain in provenance.
- Alternate source URLs and cross-source merge events are retained in `extracted_facts` for diagnostics.

## Role-family deduplication

- Same-company titles are no longer treated as duplicates solely because their normalized titles match.
- A second-stage check runs after the page has been fetched and the employer/location have been resolved.
- The check compares role-family terms, explicit job/requisition IDs, role location/country, and responsibility/content overlap.
- Different explicit requisition IDs are treated as evidence of separate vacancies.
- Clearly different locations are treated as evidence of separate vacancies unless an explicit identical requisition ID shows they are the same posting.
- Same-family roles with materially different responsibilities remain separate.
- Near-identical variants such as `Lead Linux Kernel Engineer` and `Lead Linux Kernel Engineer - Ubuntu` can collapse when the underlying evidence indicates the same vacancy.

## Company concentration guard

- Adds a rolling 14-day employer concentration check before a new Opportunity consumes another primary-list row.
- The policy is graded rather than a permanent company quota:
  - fewer than 4 recent retained roles: no concentration restriction;
  - 4-7: additional roles must be materially different or substantially stronger-fit;
  - 8-11: distinct roles also need solid fit, unless the candidate is substantially stronger than the company's retained set;
  - 12+: an additional role must be materially different and high-fit.
- Concentration is based on normalized employer identity, not the search provider. A provider can therefore remain productive without allowing one employer to flood the visible list.
- Candidates blocked only by concentration are not silently discarded. They are retained in `company_concentration_overflow` on the closest/highest-value company Opportunity, together with URL, source, query, fit, location, and policy reason.
- Concentration events are recorded in usage telemetry as `company_concentration_overflow`.

## Provider statistics and provenance

- Cross-source/role-family merges and concentration-overflow candidates count as duplicate/non-new results rather than provider-unique Opportunities.
- Campaign attribution is preserved on the retained primary Opportunity.
- Discovery provenance from every contributing provider is preserved.

## Regression coverage

- Verifies tracking-noise URL normalization and cross-source merge hooks.
- Verifies same-title/company is no longer an unconditional early duplicate rule.
- Verifies role-family logic checks explicit requisition IDs, locations, and responsibility overlap.
- Verifies the rolling 4/8/12 concentration tiers and overflow retention path.
- Verifies direct employer URLs are preferred over job-platform destinations during a cross-source merge.

No database schema change is required; migration 0192 records the release upgrade.
