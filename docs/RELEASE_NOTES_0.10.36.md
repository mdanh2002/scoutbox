# ScoutBox 0.10.36

## Changes

- Search on Opportunities, Hidden Leads, Blacklist, Address Book, Applications, and Campaigns now covers the fields represented by their current list rows, including source/target URLs. Plain host fragments such as `ycombinator` therefore match `ycombinator.com` records.
- Opportunity advanced filters use a four-column desktop checkbox layout, clearer on-site wording, Cancel / Reset / Best Fit / Apply ordering, and non-closing Best Fit selection. Best Fit excludes Unknown/Others, Older, and Evergreen post-age groups.
- Address Book URL health checks the displayed `source_url` when available, with email-domain fallback for legacy/manual contacts. Opportunities, Hidden Leads, and Address Book share semantic HTTP-200 content-warning behavior and visually dim last-known health after the existing 90-day checking window.
- Company age inferred from domain registration now exposes the exact domain and registration year in its tooltip when available.
- Direct-source Hidden Leads use a higher actionability threshold, while exceptionally niche, strongly supported company signals can still be retained.
- Local discovery prefers a verified exact employer/ATS role over a third-party job-board URL. The original board URL remains in provenance and the retained description. A one-time idle-aware upgrade backfill attempts the same repair for existing active Opportunities.
- Direct API/feed/page requests are surfaced in Search Activity and remain included in Resource Usage accounting.
- Local post-page semantic review now explicitly separates on-site/hybrid office evidence from remote work and can return a supported employer country. Post-age extraction continues to use semantic page parsing rather than site-specific string rules.
- Repetitive embedded-role fallback summaries are replaced with evidence-specific role cues where available.
- Opportunity detail actions are consistently sized and labelled Apply / Enrich / Blacklist.
- Added a default-enabled **Company career pages** Search Source. In Local AI Discovery, configured search engines can identify relevant companies and inspect their own hiring, join-team, collaboration, consulting, project, or outsourcing pages. The pipeline is disabled in Cloud Web Discovery and feeds normal Opportunity, Hidden Lead, Address Book, blacklist, and engagement-preference handling.
- Diagnostic export adds a default-checked **ScoutBox Data & Records Only** option that keeps candidate/profile, campaign, opportunity, lead, application/outreach, Address Book, relevant settings/version/configuration, and aggregate statistics while excluding high-volume operational histories.
- Retains the 0.10.35 Search Sources, About ScoutBox, and Troubleshooting presentation cleanup.

## Upgrade

Keep the existing `.env` and Docker volumes, replace the application package, and run `./restart_scout_box.sh`. Startup migrations add the Company career-pages source and the release backfill is queued through the existing background-work mechanism.

Routine future releases increment the patch component unless a larger compatibility change warrants a minor or major version increment.
