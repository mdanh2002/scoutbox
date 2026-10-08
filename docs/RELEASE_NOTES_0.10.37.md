# ScoutBox 0.10.37

ScoutBox 0.10.37 consolidates discovery-quality, retrospective data repair, source provenance, and UI feedback fixes requested after 0.10.36.

## Discovery and source quality

- Facebook Pages to Watch now requires direct Page evidence of hiring/career relevance before a discovered or manually added Page is persisted. The 0.10.37 upgrade backfill directly re-checks legacy Page rows, removes irrelevant/noisy rows, enables validated rows, and uses configured Local search providers to find a small number of additional career Pages which must pass the same direct validation.
- Company career page discovery now treats search-engine results only as pointers: candidate employer pages are fetched directly and must pass role-page and candidate-profile relevance gates before entering Opportunity ingestion.
- Direct employer/career and Facebook validation fetches are recorded in Search Activity as Direct site activity.
- Cloud AI Discovery provenance rows are removed from the Search Sources selector without deleting historical provenance. They are normalized to internal `cloud_ai` rows; Cloud discovery is controlled only by Discovery Mode, and Local AI Discovery planners explicitly ignore those rows.
- Third-party board discoveries use a stronger employer-role resolver: exact title/company search, company careers/jobs searches, direct careers-page fetching, role-link inspection, and direct ATS/employer validation. Generic careers roots remain discovery aids and are never persisted as Opportunities.

## Opportunity validity, age, remote geography, and titles

- HTTP-200 pages with explicit closed/removed language (including “applications are closed”, “no longer accepting applicants”, filled/expired roles, page/job not found, and equivalent inactive-posting text) are classified as soft 404/inactive opportunities in both discovery and URL-health checks.
- JobPosting `datePosted` and explicit visible labels such as “Posted on Aug 30, 2026” are parsed deterministically before AI date inference, improving Post Age on pages that publish clear dates.
- Explicit remote geography such as “Location requirements Poland” / “Hiring timezones Poland” overrides generic worldwide-remote guesses and is stored as a country-restricted Remote classification.
- Mixed-script stray title fragments (Hangul/CJK/Kana/Cyrillic/Arabic/Thai/Khmer) are removed from otherwise Latin/English role titles through defensive display filters and are normalized retrospectively during the upgrade backfill.
- Country-combination display such as “UK or US” chooses one recognized country for the compact list so the flag remains visible.

## Opportunity summaries and retrospective repair

- Opportunity list summaries are now concise technical cues, normally 2–6 words and one or two concrete technologies/subsystems/protocols/responsibilities. Fit explanations and constructions such as `hardware interfaces: hardware interfaces-focused embedded work` are no longer generated.
- Local and Cloud AI prompts use the same compact-summary contract.
- The 0.10.37 idle-aware backfill rewrites every stored Opportunity summary (including Recycle Bin rows so restored records are already normalized) from retained JD/evidence, cleans mixed-script titles, repairs deterministic remote restrictions, recovers explicit retained post dates where available, and continues exact employer URL recovery for third-party board records.

## UI and statistics

- Best Fit in Opportunity advanced filters now shows an inline confirmation while keeping the dialog open. Reset also stays in the dialog, resets the selections, and shows a confirmation; Apply commits the selection.
- Latest re-evaluation result banners have a close button next to History. Dismissal persists for that run and automatically reappears when a newer re-evaluation result exists.
- Company/domain-age hover help uses a real multiline tooltip: domain age, domain, registration year, size, and confidence appear on separate lines as applicable.
- Company career pages has concise hover help explaining direct employer-page validation.
- Diagnostic export’s “ScoutBox Data & Records Only” option is unchecked by default; verbose explanatory copy was removed. Rebuild Missing AI Data is hidden/removed from the maintenance UI because re-evaluation is the supported workflow.
- Left-navigation and attention badges refresh automatically every 60 seconds and again when the page becomes visible, so new Opportunities, Hidden Leads, Address Book contacts, Applications, and alert notifications appear without a full page refresh.
- Statistics adds pie charts for Opportunity Source, Leads Source, and Address Book Source normalized to Search engine, Cloud AI, and Direct search. Address Book attribution traces saved source URLs back to originating Opportunities/Leads when possible instead of relying only on contact label text.
- About adds a second short “Why use ScoutBox” paragraph. Discovery Mode now reports only `Current config: Local AI Discovery` or `Current config: Cloud` and retains the AI & Discovery link.

## Upgrade notes

Keep the existing `.env` and Docker volumes. Replace application files with the 0.10.37 package and run the normal restart/upgrade flow. Migration `0090_v01037_discovery_cleanup` non-destructively marks legacy Cloud AI Discovery selector rows as internal cloud provenance so they disappear from Search Sources without breaking historical source links. The background release repair is resumable and marks `release_backfill_version=0.10.37` only after completion.

Routine future releases increment the patch component unless a larger semantic-version change is warranted.
