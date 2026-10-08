# ScoutBox 0.9.11 Release Notes

ScoutBox 0.9.11 fixes Local Discovery query-planning model selection and Automatic Discovery queue buildup.

## Query planning follows configured Discovery routing

Campaign query planning is an internal part of URL discovery, so it now uses the exact URL Discovery Primary/Fallback route shown in AI & Discovery. Company-search query planning similarly inherits Company Enrichment Primary/Fallback. The AI Requests task stage remains `query_planning`, but its runtime/model now comes from the relevant visible route.

The query-plan cache signature also includes the Primary/Fallback route, so changing the configured models invalidates an older cached plan.

Ollama generation no longer falls back to the first model returned by `/api/tags` when no model was supplied. A blank/unresolved model is treated as a routing error instead of silently using an unrelated 1B/2B model.

## Automatic Discovery queue capacity

The scheduler now caps automatic in-flight CampaignRuns before publishing another discovery task. The default is 2, matching the standard `discovery_worker` concurrency. When capacity is full, due campaigns remain pending for the next scheduler tick and report `waiting for discovery worker — 2 active runs` in scheduler results instead of building a long Celery backlog.

The limit can be overridden with `SCOUTBOX_DISCOVERY_AUTO_INFLIGHT`, clamped to 1–8. It should normally remain at or below the discovery worker concurrency. Manual campaign runs are still allowed and count toward the in-flight total.

No database migration is added in 0.9.11.
