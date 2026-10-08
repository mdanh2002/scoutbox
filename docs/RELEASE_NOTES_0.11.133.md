# ScoutBox 0.11.133

## Global Coverage

- Adds **Global Coverage** as the default Discovery Market strategy.
- Orders markets by recent acquisition attempts rather than retained-result yield so high-yield US searches cannot consume every useful slot.
- Adds a bounded core-market lane so established markets including the UK, Australia, Singapore and Hong Kong remain in regular circulation while the worldwide sweep progresses.
- Expands Discovery Markets from the previous curated set to a country-complete catalogue of roughly 200 market entries while retaining the richer city/source metadata for curated markets.
- Existing installations that were using the complete previous default market set are expanded automatically. Deliberately customized market subsets are left unchanged.

## SearchAPI support

SearchAPI is added under **Search Sources > Sources** as two API-only providers that share a single `SEARCHAPI_API_KEY` credential:

- **SearchAPI · Google Jobs** — structured, market-localized job discovery.
- **SearchAPI · Google Web** — market-localized web search for regional job boards, employer pages, ATS discovery and source-specific `site:` searches.

ScoutBox always supplies explicit market localization (`location`, country and language) for SearchAPI calls. A SearchAPI request without a concrete Discovery Market is rejected locally so Google cannot silently fall back to United States geography.

For Google Jobs, a provider-side rejection of an explicit country code is retried only without that `gl` parameter while retaining the concrete market `location` and language. SearchAPI results with multiple application targets prefer direct employer/ATS links over aggregator mirrors. Google Web localization deliberately does not hard-restrict document language, preserving English-language employer pages inside non-English markets while native-language exploration remains available through ScoutBox's multilingual planner.

Market-specific regional-source searches prefer SearchAPI Google Web when configured. Generic source-fallback searches remain on ordinary providers because they do not have bounded market context.

## Regional-board resilience and country provenance

- Structured Google Jobs records are treated as direct source evidence. If the linked destination temporarily blocks automated retrieval with a non-404/410 response, ScoutBox can still run its normal semantic qualification against the structured source text instead of discarding the role solely because the board returned a block page.
- Market-specific regional-board searches preserve a bounded market-location hint. Explicit current-role fields, structured JobPosting locations and eligibility evidence remain higher priority.
- The upgrade conservatively repairs legacy blank/United-States countries when the concrete Opportunity target/URL itself belongs to a known country-specific board domain, including JobsDB Hong Kong, JobStreet Singapore/Malaysia/Philippines, SEEK Australia/New Zealand, Reed UK and several European/Asian regional sources.

## Multilingual discovery

- Foreign-language pages found by ordinary market queries can now be translated from explicit query language, market-native language or detected language evidence.
- Translation is no longer limited to the small subset of queries explicitly tagged multilingual.
- Low/Balanced/High multilingual exploration budgets scale with enabled-market footprint and remain bounded to protect provider usage.
- Native market-language pairs rotate across campaigns, so Spanish/French/Portuguese/Arabic markets do not all compete for a single global language slot.
- The expanded world catalogue assigns common discovery-language defaults across Latin America, Francophone/Lusophone Africa and MENA instead of silently treating new markets as English-only.
- Translated pages continue through the same strict role, candidate-profile, remote and persistence gates used for English pages.

## Reliability and compatibility

- Search-provider selection reserves configured SearchAPI providers so a newly connected SearchAPI account receives enough localized work to establish real market-level yield.
- The provider budget is re-checked immediately before each campaign provider slice so concurrent runs cannot knowingly start a slice larger than the remaining daily allowance.
- Local-source search coverage per run is configurable with `SCOUTBOX_MARKET_SOURCE_QUERIES_PER_RUN` and defaults to 16, bounded from 4 to 32.
- 0.11.132 re-evaluation reliability safeguards and dialog fixes remain intact.
