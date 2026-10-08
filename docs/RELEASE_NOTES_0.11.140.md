# ScoutBox 0.11.140 — Facebook Page Identity Titles

- Fix Facebook Pages title extraction so indexed hiring/post headlines are never stored as the Page title.
- When Facebook direct metadata is unavailable, require indexed titles to match the known Page identity; otherwise fall back to the stable Facebook vanity Page ID.
- Split CamelCase vanity IDs into readable Page names and expand the `NA` suffix to `North America`, so `BoschBuildingTechnologiesNA` is displayed as `Bosch Building Technologies North America` rather than a hiring-post headline.
- Migration 0212 repairs existing Facebook Page rows whose stored title is clearly a post/hiring headline while preserving Discovery Evidence separately.
- No discovery-source, SearchAPI, Opportunity, Hidden Lead, campaign, or Facebook evidence behavior is otherwise changed.
