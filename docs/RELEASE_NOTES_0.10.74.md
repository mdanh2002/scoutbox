# ScoutBox 0.10.74

- Forum browsing now runs as an independent bounded campaign pass so slow normal search-engine stages do not starve forum source coverage.
- Added forum-only campaign run metadata and scheduler isolation so forum passes do not block normal runs and normal runs do not block forum passes.
- Added stale-run release migration for existing stuck forum/search rows after upgrade.
- Normalized outgoing `site:` search operators to host-only constraints to avoid malformed path-scoped queries such as `site:facebook.com/posts`.
- Updated Facebook indexed-search query generation to use `site:facebook.com` only, with relevance handled after retrieval.
