# ScoutBox 0.10.79 release notes

## Discovery throughput

Forum/community acquisition is now supplementary by construction. Automatic Forum passes are queued only when there are no primary CampaignRuns and no BackgroundJob of any kind in queued/running state, use a dedicated single-concurrency `forum` Celery worker, and are excluded from Local/Cloud primary scheduling counters. A global 30-minute throttle prevents many campaigns from turning the per-campaign interval into continuous Forum traffic. A Forum worker checks for newly queued primary work between bounded operations and yields rather than waiting for scarce Local AI capacity. Local Forum qualification gets only a non-blocking Ollama-lane attempt and a short request cap; Cloud Forum qualification is capped to one route attempt/one candidate with a 30-second request ceiling, reduced token caps, no empty/structured retry or failover, no rate-limit backoff, and Forum-only 429s do not trigger the primary Cloud scheduler cooldown. The default Forum pass is limited to 60 seconds of source acquisition, three Forum adapters, one AI-qualified candidate and no recursive follow-up pages. Reddit retains its own request/query/error/time circuit breakers.

The normal Local AI and Cloud Web campaign paths no longer execute Forum adapters inline. Cloud Web still supports Forum discovery through the same idle Forum path, using Cloud qualification only for the bounded candidate slice. Higher-priority Hidden Leads/background scheduling is evaluated before Forum scheduling in each scheduler tick. Forum-only runs do not update `Campaign.last_run`, the primary `PortalSettings.last_discovery_run`, or count against `cloud_auto_runs_per_campaign_day`.

The concrete 0.10.78 Forum-only crash is fixed: `forum_source_rows()` now accepts and forwards `stage_budget_seconds` and `max_sources`. Maintenance recovery also requeues Forum-only CampaignRuns onto the dedicated `forum` queue rather than the primary discovery queue.

## Search/direct-source balance

Search engine ordering and per-run query allocation now use rolling seven-day `SearchProviderStat` evidence plus the current retention state of recently created Opportunities and Hidden Leads. Retained results are rewarded, recycled/suppressed output, high error rates and substantial zero-yield traffic are penalized, degraded engines receive only a recovery probe, and one provider slot rotates for exploration/recovery. Low-yield but retained engines receive a smaller diversification slice instead of the same query volume as proven high-yield engines. This keeps productive engines such as those actually retaining opportunities from being diluted by repeated high-error/zero-yield work without permanently disabling any configured engine.

Non-Forum direct adapters remain enabled because they have demonstrated useful retained yield. They are adaptively ranked by seven-day yield, current retention and error rate, execute after the primary search-engine or provider-native Cloud stage, and have independent source/time/candidate caps. If the available catalog is dominated by known-bad sources, ScoutBox probes only one degraded source rather than filling every source slot with failing adapters. This prevents a large direct feed from reducing primary acquisition coverage.

## Cloud AI reliability

Gemini 3.x empty-visible-output responses now receive one targeted same-model retry using minimal thinking and without forced JSON MIME, followed by the existing configured route failover when needed. The behavior applies to both Cloud Web grounded research and ordinary Cloud generation routes, including direct/Forum candidate qualification. Empty attempts retain provider-reported token/reasoning accounting rather than being reconciled as zero usage. Provider capability testing uses the same targeted Gemini retry.

## Discovery quality

Hidden Leads now require first-party organization evidence in addition to niche keyword/activity overlap, reducing technical articles, community pages and personal posts that happen to contain campaign terms.

Address Book generic-mailbox detection now recognizes additional functional/shared local parts including `marketing`, `campaigns`, `recruit`, `recruiter`, `work`, `askhr`, `peopleops`, communications/community/partnerships and business-development forms. Migration `0108_v01079_contact_generic_repair` repairs the `generic` flag on existing matching contacts without deleting any Address Book entry.

## Upgrade note

Docker Compose adds a `forum_worker` service. Deploy the full Compose stack so the new `forum` queue has a consumer. Existing primary `worker` and `discovery_worker` services retain their prior responsibilities.
