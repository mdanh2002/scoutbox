# ScoutBox 0.10.103 release notes

## Country and location integrity
- Candidate/profile operating locations are no longer supplied as country evidence during Opportunity discovery or re-evaluation.
- Opportunity country resolution is evidence-grounded: structured JobPosting location, direct-source location, explicit page role/eligibility location, retained grounded role location, then verified company HQ only for genuinely remote roles with no role-country restriction.
- Bare model country guesses are not persisted as Opportunity country values.
- Direct RemoteOK, Remotive, Himalayas and Jobicy adapters retain their role-location fields as provenance for deterministic location resolution.
- A one-time post-upgrade background job repopulates country/location fields across existing Opportunities, Hidden Leads and Address Book contacts. It corrects records when stronger source/page/company evidence exists and clears legacy Opportunity country values that can be traced only to old ungrounded AI guesses when no grounding can be recovered.
- Company research no longer treats Opportunity.country as employer-HQ evidence.

## Facets and compact list presentation
- `All countries (N)` on Opportunities and Hidden Leads now represents the complete result universe with the country filter removed, including rows whose legacy country is blank/unrecognized. Named country choices remain canonical country-only counts.
- Opportunity and Hidden Lead HTTP-status badges use the same compact 8px/padded treatment as Address Book summary badges.
- The `primary campaign runs · 2–10` helper is removed from General settings while the 2–10 validation constraint remains unchanged.
- Unknown Post Age (`?`) renders without a tooltip/ARIA tooltip payload on Opportunity and Campaign lists.

## Full-result sorting
- Blacklist Date Added sorting is performed before pagination, so it orders the full filtered database result rather than only the current page.
- The same current-page-only sorting defect was removed from the other server-paginated tables that used the generic client sorter: Opportunities, Hidden Leads and Recycle Bin.
- Their sortable headers now use explicit server/full-result sort modes; filters, page size and exports preserve the selected ordering.
- Small client-only tables that already contain their complete dataset retain client-side sorting.

## Domain age / RDAP
- Domain registration lookup now resolves each TLD's authoritative RDAP endpoint from the IANA DNS bootstrap and caches the mapping for 24 hours.
- `.io` and other non-`.com` domains therefore use their registry service rather than depending on one generic aggregator path.
- RDAP creation/registration events are accepted; last-change/updated events are never used as a fabricated creation date.
- Authoritative registries such as `.de` that do not expose a registration/creation date are marked unavailable instead of being retried forever.
- Transient network/HTTP failures remain retryable and store endpoint/source/error diagnostics for maintenance.
