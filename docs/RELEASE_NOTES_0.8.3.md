# ScoutBox 0.8.3 release notes

0.8.3 focuses on result quality, compact UI, provider testing, continuous niche discovery and safer operational workflows.

## Result quality
ScoutBox now treats search-engine results as discovery pointers. It resolves and fetches the target page, records Search URL and Target URL separately, strips redirect boilerplate and applies a deterministic role-quality gate before normal Opportunity ingestion. Documentation/manuals, media pages and generic technical/product pages are rejected or strongly down-ranked; PDFs receive a significant penalty but can survive when role evidence is strong. Non-English results remain visible with a language indicator and a ranking penalty rather than being blindly removed.

A new Blacklist blocks configured domains/paths from both Opportunity and Hidden Market ingestion. It is seeded with common documentation/reference/media sources and can be extended manually or from an individual result.

## Continuous discovery
The configured search interval is a discovery window rather than a single fixed attempt. Enabled campaigns rotate queries/providers repeatedly within that window, with bounded attempt counts and error-aware backoff. Hidden Market scans also run automatically and look for evidence of relevant technical work, not only explicit hiring phrases.

## Search-provider configuration
Search Sources is compact by default. Engine names open a configuration/test modal where supported API credentials can be stored and an arbitrary keyword can be tested. The test displays parsed result titles, target URLs and snippets so failures are visible before a campaign is run.

## UI and workflow
CV/Cover versions link their original files without a separate Original column. Search Scope uses compact wrapping controls and multiple pay preferences. Campaign Designer uses compact token controls and improved action placement. Opportunity/Cold Contact lists use semantic SVG controls, language indicators and timestamps. Export uses one consistent download icon.

Dashboard activity charts now switch between Today, Week, Month and Year with hour/day/month aggregation and display Searches, Opportunities, AI tokens and Errors. Dashboard activity, Statistics & Funnel and Usage & Resource Telemetry refresh in the background every 30 seconds and show last-updated timestamps. A new Activity Pulse above the dashboard rotates representative current/recent work (campaign jobs, search-provider queries, target-page reads, AI analysis and captured opportunities), while Apply/Review/Information/Replies counters refresh every 60 seconds without a page reload.

## Mail, contacts and AI
Email configuration combines the IMAP connection/folder test and keeps long tests asynchronous. Email History supports complete plain/HTML bodies and delivery status. Address Book inference suppresses obvious no-reply/sales addresses and falls back to a domain/company label when no person name is available.

AI provider rows are more compact, test prompts sit below model configuration, local default wording is simplified to Default, and cloud providers have an explicit output-token safety cap. Performance Lab tests remain asynchronous and include post-age analysis using ScoutBox's freshness logic.
