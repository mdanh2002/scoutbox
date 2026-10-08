# ScoutBox 0.11.116

ScoutBox 0.11.116 focuses on discovery quality, support-export completeness, and reducing repeated low-yield work.

## Support export

- Support record exports now include retained **Facebook Pages** and **Tracking Links**, including rows moved to the Recycle Bin during the selected export period.
- Tracking Link records include their rule name and related Application/Opportunity identifiers where available.
- Facebook Page and Tracking Link counts are included in the diagnostic summary and recycle-bin section.
- Diagnostic export format advances from version 4 to version 5. Diagnostics-only exports continue to omit these user records.

## Hidden Leads quality

- Hidden Leads now require a practical outreach/commercial signal in addition to technical similarity. Balanced mode requires a clear current reason to contact or track the organization; purely topical/technical pages no longer qualify by themselves.
- Deterministic outreach evidence covers consulting/engineering services, project/vendor/partner signals, sales/contact intent and active hiring evidence. Recently rejected Opportunities remain a valid company-level hiring signal for bounded salvage.
- Hidden Lead scoring gives explicit outreach evidence material weight instead of allowing technical keyword overlap to dominate.
- Automatic Hidden Lead additions are capped by Lead Selectivity: Broad 10, Balanced 7, Specialist 4 per scan (including Opportunity salvage).
- Hidden Lead search patterns favor company/service/outreach evidence over generic technical-content searches.

## Markets and multilingual Hidden Lead discovery

- Hidden Lead scanning now uses the configured **Discovery market strategy**, including Balanced market rotation.
- The configured multilingual exploration strength is honored. Balanced schedules up to two supplemental translated Hidden Lead searches per scan budget; Low/High continue to use their configured caps.
- Technical terms are protected while natural-language query words are translated.
- Foreign-language pages found by an explicitly multilingual Hidden Lead query are translated for qualification instead of being immediately discarded. Accidental foreign-language pages from ordinary English searches remain subject to the normal language gate.
- Hidden Lead market/language searches are recorded as real provider queries and in discovery-market telemetry, making multilingual activity visible in Search Activity/diagnostics.

## Search-provider saturation controls

- Main Local AI campaign searches now have a default hard ceiling of 12 queries per provider per run (`SCOUTBOX_PROVIDER_QUERY_HARD_CAP` can override it downward/upward), even if the saved per-provider setting is much larger.
- Provider query allowance now checks a two-day window before the seven-day history. Providers with substantial recent traffic but zero new retained/unique value, or severe recent error rates, fall back to a one-query recovery probe.
- Degraded-provider global recovery probes default to every six hours instead of every four hours.

## Direct ATS efficiency

- Greenhouse, Lever, Ashby and SmartRecruiters direct-source passes remove exact Opportunity URLs that ScoutBox already retains before those rows reach fetch/AI qualification.
- Direct-source diagnostics report how many known Opportunity URLs were skipped per source.

## Facebook Page identity

- Search-index Facebook Page discovery now matches Page IDs case-insensitively, reducing duplicate Page watches caused by capitalization variants.
- Rediscovery no longer re-enables a Facebook Page that the user has moved to the Recycle Bin.

No schema change is required. Migration 0188 records the release upgrade.
