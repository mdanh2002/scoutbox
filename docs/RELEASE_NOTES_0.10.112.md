# ScoutBox 0.10.112

## Fixed

- Preserves recruiter/job-board role locations for display before expanded structured eligibility. A Jobicy role published as `LATAM` no longer becomes an arbitrary list of Latin American countries.
- Treats common recruiter regions as first-class location values, including LATAM, APAC, ASEAN, EMEA, MENA, GCC, ANZ, DACH, CEE, Benelux, Nordics, EU/EEA, UK & Ireland, Americas and Worldwide.
- Excludes campaign names from deterministic Focus topic-rule matching. A campaign named `Embedded Jobs` can no longer make an unrelated QA, support or backend role satisfy `Embedded Firmware`.
- Adds a content-grounded `QA & Testing` Focus rule and performs a controlled full Focus rebuild during the upgrade.
- Adds a no-progress cooldown to blank-Focus maintenance so persistent unclassifiable rows do not create a background repair every scheduler tick.
- Makes `~ 3 days` the canonical Post Age for 0-6 days and `~ 1 week` for 7-13 days across persistence, display, sorting and repair. Exact retained dates now outrank stale cached age counters/legacy labels.

## Changed

- Original job-board evidence now retains role-location wording so later employer/ATS resolution does not discard a recruiter-published region.
- The 0.10.112 upgrade re-normalizes retained Post Age data and resets the one-time evidence-grounded location repair so existing affected records are corrected after deployment.
- Worldwide source-domain expansion recognizes campaigns that start from any known family member, not only the default/global domain.

## CR-3 completion

- Keeps the default/global domain in known source variant families and continues bounded `site:` expansion without changing Google/Bing locale or adding UI settings.
- Adds provider-supported direct endpoint variants to the internal source map. Lever direct discovery now tries the learned/default endpoint plus the supported global/EU counterpart with a two-endpoint source cap.
- Direct-adapter rows are deduplicated across endpoint variants. Sources with only one global API continue to make one endpoint request; ScoutBox does not invent regional APIs.
