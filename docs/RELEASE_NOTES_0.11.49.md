# ScoutBox 0.11.49

## Changes
- Global Activity Map legend counts now show only records currently represented by map markers, e.g. `Blacklist (15)`, rather than mixing mapped and total database counts.
- The same mapped-only count behavior is used for Opportunities, Hidden Leads, Contact, Applications/Outreach, and the PNG export legend.
- Added a small right-aligned hint beside `Global Activity Map` explaining that items can be omitted when location data is unavailable or insufficient.
- Added bottom spacing below the Global Activity Map card.
- Fixed precise markers being visually displaced from their true coordinates by deterministic anti-overlap jitter; precise city/coordinate markers now stay on the exact projected position.
- Fixed misleading location resolution caused by scanning general company names, titles, URLs, descriptions, and snippets for city names.
- Progressive map resolution now uses location-bearing fields only. AI-resolved locations must also be explicitly supported by the supplied location evidence instead of inferred from company identity or unrelated page text.
- Bumped the Statistics map location cache namespace to `stats_map_geo_v3`, so locations cached by the older permissive resolver are ignored and can be safely rebuilt.
- Blacklist location reuse remains evidence-based but now derives coordinates only from matched records' location fields/structured location payloads, not company names or URLs.
- Existing safeguards against TLD-based location guesses and broad Worldwide/large-country centroids remain in place.

## Validation
- Added ScoutBox 0.11.49 regressions covering mapped-only legend counts, the missing-location hint, bottom spacing, cache invalidation, and location-only resolution inputs.
- Python AST parse and compileall.
- Statistics JavaScript syntax check.
- Docker Compose YAML parse.
- Shell syntax checks.
