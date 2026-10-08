# ScoutBox 0.10.80 release notes

## Primary discovery always wins

0.10.79 separated Forum/community work onto its own Celery worker, but a Forum pass could still start during the waiting gap between primary campaign rotations. Even with separate worker slots, Forum HTTP requests and optional AI qualification share network, database, Ollama/GPU or Cloud-provider resources. On a low-yield Forum catalog this could make Search Activity appear to switch from useful search-engine work to a sustained Forum burst.

0.10.80 changes Forum scheduling from merely `no primary run is active` to **deep idle**. In Local AI Discovery, every enabled campaign must first complete its planned primary search rotations for the current search window, and the next window must not be inside the Forum guard period. In Cloud Web Discovery, no primary Cloud campaign may be due inside that guard period. Any queued/running primary CampaignRun or BackgroundJob still blocks Forum scheduling, and an already-running Forum task continues to yield as soon as higher-priority work appears.

Forum work is also much smaller by default: one Forum source per pass, 25 seconds of source acquisition, one listing URL, at most one broad native-search fallback, 5-second request timeouts, two-hour Forum response caching, one AI-qualified candidate and no recursive follow-up pages. JSON endpoints no longer repeat a failed connection/HTTP request as a second text request; text fallback is reserved for reachable endpoints that fail JSON decoding. The Forum adapter now receives the cooperative stop callback directly and checks it between HTTP operations.

These rules apply in both discovery modes. Cloud Web continues to allow Forum discovery, but Forum work remains supplementary and cannot become the workload that determines Cloud discovery cadence.

## Search-engine balance

The adaptive seven-day retained-yield/error scoring from 0.10.79 remains. 0.10.80 additionally makes degraded-engine recovery probing global rather than per campaign. A high-error or established zero-yield engine is eligible for at most one recovery probe during the configured cooldown window (four hours by default). Other concurrent campaigns do not create additional Yahoo/Startpage/etc. probe bursts while that cooldown is active. Productive and retained engines keep their normal or diversification query allocation.

## Upgrade

No migration is required. Deploy/recreate the full Compose stack as with 0.10.79 so the dedicated `forum_worker` remains active. Existing `.env` files continue to work. The one-source and 25-second Forum limits, the minimum Forum scheduling intervals, and the request/listing caps are enforced as safety ceilings/floors in code, so older looser Forum values cannot restore the high-throughput Forum behavior. The new `.env.example` reflects the effective safe settings.
