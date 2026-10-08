# ScoutBox 0.8.120 release notes

## AI Request JSON wrappers

AI Request Input/Output now strips ordinary and escaped Markdown JSON wrappers before validation, including ` ```json ` / ` ``` json ` forms and shortened closing fences. The JSON tree is shown only when the normalized whole payload parses as JSON; arbitrary prose containing a JSON fragment remains text.

## Opportunity salary presentation

High/Medium/Low salary-confidence wording is no longer printed beside advertised salary values. Confidence remains stored internally for scoring/provenance.

## Dashboard alignment

First Run Readiness detail/count text now starts at the same horizontal position as the Date column in Recent Campaigns.

## Local search-provider rotation

The Local AI Discovery provider selector previously sorted by a hard-coded locale tier before daily utilization. Because each run selects four providers and Google/Bing/DuckDuckGo/Brave occupy the first tier, lower tiers could remain unused indefinitely while those four stayed usable. 0.8.120 sorts first by normalized daily utilization and uses locale tier as a tie-breaker. This keeps strong English engines first on a fresh day but rotates through enabled alternatives on later runs. Cloud Web Discovery does not use this selector and is unchanged.

No database migration is added in this release.
