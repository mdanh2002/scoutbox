# ScoutBox 0.11.134

## Community hiring-signal redesign

- Reddit, Hacker News, Lobsters, DEV hiring, Indie Hackers and generic forum adapters are explicitly marked as community hiring-signal sources.
- Community posts are preserved as post-level evidence instead of being treated as aggregate job pages and expanded into arbitrary outbound links.
- Local Source Guided discovery can turn a candidate-relevant hiring/project/outreach post into a Hidden Lead even when there is no canonical ATS vacancy URL.
- A fetched, concrete item-level vacancy can still pass the normal Opportunity gates; snippet-only or generic community evidence is always downgraded to a Hidden Lead signal.
- Community Hidden Leads are keyed by actual employer identity, not by the shared platform domain, so deleting one Reddit/HN lead cannot suppress unrelated employers.
- Cloud Web forum qualification now has a dedicated hiring-signal verifier. Community signals can become Hidden Leads without being forced through vacancy-only remote/exact-URL rules and without invoking Local AI.

## SearchAPI Discovery expansion

- Renamed the Search Sources group from `Search APIs / SERP` to **SearchAPI Discovery**.
- Added **SearchAPI · Google Forums** as a supplemental market-localized community discovery engine.
- Added **SearchAPI · Google News** as a supplemental recent hiring/expansion/project signal engine.
- Google Forums uses a recent-month window, resolved destination links and SafeSearch.
- Google News uses a recent-month window, most-recent ordering and resolved destination links.
- Both engines share the existing `SEARCHAPI_API_KEY` with SearchAPI Google Jobs/Web.
- All SearchAPI engines now share one daily request/credit budget pool rather than receiving separate copies of the configured API-provider budget.
- SearchAPI Forums/News are excluded from the ordinary search-provider competition and run only in bounded supplemental lanes.
- The Forum-only Source Guided pass can use SearchAPI Google Forums as a resilient fallback when native Reddit/community endpoints fail.

## SearchAPI modules considered

Google Local / Google Maps are potentially useful for future employer discovery: they can identify regional companies, websites and addresses even when the companies have poor job-board visibility. They are not enabled in this release because ScoutBox first needs a dedicated employer-discovery budget/quality lane; feeding general local-business results directly into Hidden Leads would create unnecessary noise. Google Local is the preferred next candidate because it accepts canonical location text, whereas Maps is more naturally coordinate/radius driven.

## Preserved from 0.11.133

- Global Coverage scheduling and worldwide market catalogue.
- Explicit SearchAPI market localization and Google Jobs/Web support.
- Regional-board acquisition and blocked-board structured-evidence fallback.
- Country provenance improvements and conservative legacy false-US repairs.
- Ordinary-query multilingual page translation.
- 0.11.132 re-evaluation reliability and dialog-layout safeguards.
