# ScoutBox 0.11.62

## Location, map and list-view integrity

- Statistics no longer shows the live `Last updated` timestamp in the date toolbar; Export remains the rightmost control while live metric refresh continues in the background.
- Source-native recruiter regions such as LATAM, APAC, EMEA and Europe are preserved instead of exposing provider-expanded structured country arrays. Jobicy `Remote from` parsing now also recognizes broad regions across flattened/markdown page layouts.
- Opportunities use source-faithful location records for list filtering/display and the Statistics map; old large structured JobPosting country arrays are suppressed unless retained source evidence identifies a broad region.
- Shared sticky list toolbars now sit flush below the 55px global header on supported list views.
- Global Activity Map coordinate caches move to `stats_map_geo_v4` and include a location-evidence fingerprint, so changed location evidence cannot reuse stale coordinates.
- Map markers that occupy the same visual area are aggregated. Legend numbers now represent rendered pins rather than the number of underlying records hidden under overlapping markers; aggregated tooltips report the number of records at that location.
- About ScoutBox now uses a single separator above the queued-job troubleshooting note.
- Resource Usage `Usage Events` remains unchanged in this release.
- The previously discussed US-heavy discovery/source-market imbalance is intentionally not changed in 0.11.62.
