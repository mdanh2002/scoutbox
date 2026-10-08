# ScoutBox 0.10.32

0.10.32 introduces Fresh Source Discovery to improve Opportunity freshness and reduce dependence on search-engine caches.

- Fresh direct acquisition runs before ordinary search discovery in both Local AI and Cloud AI modes.
- Added direct current-job adapters for Remote OK, Remotive, Himalayas and Jobicy, plus We Work Remotely RSS.
- Added direct public ATS adapters for employer boards already learned by ScoutBox: Greenhouse, Lever, Ashby and SmartRecruiters.
- Added Hacker News Who is Hiring acquisition using the latest monthly thread and direct HN comment retrieval.
- Added Reddit direct search using OAuth credentials when configured, with Reddit's own JSON search endpoint as a no-credential fallback.
- Campaign/profile relevance and freshness are applied before candidates enter the AI qualification pipeline.
- Direct source item IDs, acquisition path, board/thread provenance and source-last-seen information are persisted with Opportunities.
- Authoritative direct publication timestamps are preferred for freshness. Greenhouse `updated_at` is retained only as source metadata and cannot manufacture a Post Age.
- Search-engine query planning skips Direct-capable presets as explicit `site:` targets, while general search remains available as supplemental discovery.
- Search Sources identifies Direct-capable presets and Statistics reports Opportunity quality by acquisition path.
- Added Jobicy to the built-in source catalog and a dedicated Fresh job feeds / communities category for Hacker News Who is Hiring.

Migration `0086_v01032_fresh_source_discovery` updates Search Source capability metadata and adds the Jobicy preset. It does not change the database schema.

Routine future releases increment the patch component unless a larger version change is explicitly requested.
