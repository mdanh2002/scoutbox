# ScoutBox 0.10.116

Hotfix release.

- Startup migrations are database-only and fast; no external page fetches, LLM calls, or bulk repairs run before web health.
- Source/location repair runs after the portal is healthy as a Dashboard Activity background job.
- Opportunity location extraction is source-scoped across job boards, ATS pages, direct company career pages, local discovery, and Cloud/local fetched pages.
- Current role location fields override structured arrays, body inference, and LLM inference. Related/recommended job cards, footer/company panels, marketing prose, and product text are ignored.
- Jobicy examples such as Upstart USA, Skylum Europe/Ukraine, and Phantom USA/Europe are covered by deterministic extraction rules.
- Worldwide/Global/Anywhere remain blocked from persisted location fields.
