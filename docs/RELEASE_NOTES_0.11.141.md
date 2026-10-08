# ScoutBox 0.11.141 — Source Coverage Integrity

- Fix Local AI Discovery source starvation by removing the pre-rotation 32-expanded-domain cutoff.
- Schedule enabled source identities first and choose one rotating domain-family variant only after a source receives a slot.
- Use bounded source rotation so every enabled ordinary source is selected within a calculable number of campaign rotations.
- Keep source identity/provenance metadata on source-targeted query-plan rows.
- Filter unconfigured credentialed direct adapters before applying the direct-source execution cap.
- Reserve direct-source coverage slots for the longest-idle configured sources while retaining performance-ranked slots.
- Execute coverage candidates first so the direct-stage wall-clock budget cannot repeatedly expire before exploration runs.
- Make direct-source search-engine fallback use the full adapter-capable pool rather than the capped direct selection, with one domain variant per source per pass.
- Add a dedicated `yc_jobs` adapter for YC Work at a Startup using YC-owned job surfaces; remove YC job pages from the Hacker News Who is Hiring adapter.
- Record complete `domains_touched` metadata for direct-adapter Search Activity rows, independently of the first 12 displayed URLs.
- Migration 0213 upgrades existing YC Work at a Startup source rows to the direct `yc_jobs` adapter without changing operator-owned enabled/priority settings.
- Preserve all 0.11.140 and earlier behavior outside source scheduling/acquisition coverage.
