# ScoutBox 0.10.66

0.10.66 is a forum discovery reliability patch on top of 0.10.65.

## Fixes

- Runs Forum browsing/listing-page acquisition as a dedicated bounded discovery stage before ordinary direct sources and before normal search-engine queries.
- Keeps Forum candidates from being crowded out by ordinary direct feeds during Cloud Web direct-source qualification.
- Lets Automatic Local Discovery queue a campaign when enabled direct/forum sources are available, even if no normal search engine is currently selectable.
- Ignores stale queued/running campaign rows when deciding whether a campaign is already active.
- Lowers the default stale-heartbeat finalization threshold to 75 minutes so dead campaign runs do not block the next scheduled Forum pass for hours.
- Adds an upgrade migration that releases already-stale queued/running campaign rows during upgrade.
- Preserves marketplace/listing-first Forum browsing and keeps narrow native forum keyword searches as fallback only.

Routine future releases increment the patch component from 0.10.66.
