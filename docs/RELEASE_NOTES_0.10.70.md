# ScoutBox 0.10.70

0.10.70 improves direct-source discovery and cleans up diagnostics/UI noise.

- Direct source adapters that use keyword/API search now rotate across compact campaign-aware specialties, roles, engagement terms and profile skills instead of repeatedly using one static role phrase.
- Reddit direct discovery now issues varied native Reddit searches while keeping Reddit's existing adapter ownership intact.
- SmartRecruiters direct discovery browses open company boards first and uses rotated keyword fallback only when needed.
- Search Activity now records direct-source query labels in metadata and shows forum browsing rows with the forum URL and count of checked URLs where available.
- Search Activity latency displays as milliseconds up to 1000 ms, then as seconds with one decimal place.
- Automatic Address Book promotion writes audit entries only when a contact is created/updated by default; noisy skipped attempts remain suppressible unless verbose promotion audit logging is explicitly enabled.
