# ScoutBox 0.9.41

## Hidden Leads — Company Info

Hidden Lead qualification now keeps compact company metadata from the same Cloud Web research pass that decides whether a lead is directly actionable. When supported by public evidence, ScoutBox preserves employee count/range, founding year, founder, and the supporting company-info URLs before the lead is persisted.

This does not add a second AI request. It reuses the existing Hidden Lead qualification response.

Existing Hidden Leads can already contain useful company research even when the age/size subset is unavailable. In that case the Hidden Leads list now shows a neutral **Info** indicator with a tooltip containing retained company facts instead of showing `?`. Opportunities and Address Book keep their existing Company Info behavior.

## Cloud persistence diagnostics

`cloud_persistence_rejections` now records post-verification reasons that previously returned before incrementing the collector. This includes confirmed 404/410 targets (`dead_url`), target-fetch failures, search-engine targets, blacklisted targets, job-board/collection URLs, and aggregate search-result pages. Existing reasons such as `generic_url`, `multi_role_page`, `remote_ineligible`, and `closed_or_expired` remain unchanged.

This is diagnostics-only for Opportunities: no Opportunity eligibility, remote, URL, freshness, scoring, duplicate, or persistence rule is loosened or tightened.

## Compatibility

No database migration is added in 0.9.41. All 0.9.40 UI fixes are retained.
