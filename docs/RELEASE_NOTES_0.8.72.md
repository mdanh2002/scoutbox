# ScoutBox 0.8.72 release notes

## Cloud Web discovery

- Cloud Web is a hard run-level mode. Campaign runs snapshot the selected discovery method; Cloud runs do not use the Source-Guided query planner, local Ollama classification/freshness paths, or local search-engine discovery. Search/Ollama entry points reject accidental Cloud-run calls.
- Scheduled Cloud runs no longer launch the legacy local Hidden Market scanner. Cloud research itself can return selective `hidden_lead` discoveries.
- Each Cloud research pass targets one role. ScoutBox chooses the best active CV by extracted-text relevance using the configured Cloud provider, with no filename-based or role-name hard coding, then creates a compact role definition, specialist evidence and title/work angles from that CV.
- The initial Cloud request no longer serializes the full profile/campaign. Raw campaign `extra`, role arrays, technology dumps and `recency_days` are omitted. One normalized selected CV is supplied as supporting evidence.
- Direct inspection reads every URL returned by Cloud AI without using a local search engine. Public visible/`mailto:` email addresses can create or enrich Address Book records; evidence-backed interesting non-matches can become Hidden Leads.
- Opportunities still require an exact item-level URL and verified remote/geographic eligibility. Pay, company size, engagement type and hiring-process preferences are soft ranking signals only.

## Cloud result reliability and Post Age

- Cloud discovery/verification uses a practical 8,000-token output default (bounded by the provider/model maximum) instead of the previous 2,000-token default that frequently truncated structured results.
- Verification uses batches of at most two candidates and retries missing/invalid/truncated candidates one at a time. A structurally unusable verifier result fails visibly instead of silently becoming a successful empty campaign.
- Provider finish reason, configured output cap and a truncation flag are recorded in AI Request metadata where available.
- Cloud Post Age research may cautiously infer or guess an age when no explicit date exists. Cloud AI may use ordinary web research including archive.org evidence, but ScoutBox does not call an archive.org API. Direct page/HTTP evidence is also retained.
- Best-date values within today ±1 day are suppressed unless explicitly stated by the actual opportunity item. Post Age cells are centered.

## Source-Guided discovery

- Outbound local search-engine queries preserve quoted phrases and `site:` constraints while removing Boolean `AND`, `OR`, `NOT`, grouping punctuation and pipe alternatives. ScoutBox performs exclusions/filtering after retrieval.
- Query planning rotates more role aliases/context and extracts specialist technologies directly from active CV text, including terms not present in the built-in skill graph.
- Startup/small-team preferences produce corresponding natural search angles. Secondary preference mismatches do not exclude an otherwise valid niche opportunity.

## Quotas, diagnostics and UI

- Untouched Cloud defaults are raised to practical research levels: 60-minute automatic interval, 16 auto runs/campaign/day, 100 Cloud requests/run, 120 native searches/run, 50 discovery candidates/run, 30 deep-research candidates/run, 1,200 requests/day, 2,000 native searches/day, 5M input tokens/day, 750k output+reasoning tokens/day, 100 passive enrichments/day and 50 page recoveries/day.
- The migration upgrades only old default values and raises untouched cloud-provider 2,000-token caps to 8,000; custom values remain unchanged.
- Notifications warn when local search-provider quota, Cloud daily quota, or a recent Cloud run's request/search/candidate quota is fully consumed.
- Engagement Preferences no longer implies those preferences are ignored in Cloud Web. Search Sources keeps the correct Cloud warning with clean punctuation.
- AI Request Campaign/Run mapping works for task-style Cloud stages such as `url_scrape`. The detail popup shows full payloads with JSON highlighting and copy buttons. XLSX payloads are losslessly chunked past Excel's cell limit; JSONL preserves raw records.
- Telemetry is titled `CPU, RAM & Tokens` with repaired right-side axes and distinct series.
- `Keep until` is renamed `Maintain custom instructions until`.
- Maintenance cleanup permanently removes recycle-bin Opportunity/Hidden Lead rows when clearing generated workspace data; full workspace reset also clears recycle-bin workspace records.

## Upgrade

Keep the existing `.env` and volumes, replace application files with this package, then run:

```bash
chmod +x restart_scout_box.sh
./restart_scout_box.sh
```

Migration `0040_v0872_cloud_limits.py` is applied by the normal restart process.
