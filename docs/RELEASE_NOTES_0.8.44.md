# ScoutBox 0.8.44 release notes

ScoutBox 0.8.44 is a cloud-cost, AI-readiness, analytics and cross-platform release built from the known-good 0.8.43 source. The established Local GPU/Ollama source-guided discovery path is preserved materially unchanged; when a web-capable cloud route actually executes discovery or research, ScoutBox uses a lower-query cloud-native path.

## Cloud-native discovery and OpenRouter

- OpenAI, Gemini and OpenRouter can perform broad web-connected opportunity discovery instead of mechanically expanding thousands of keyword/search/scrape operations.
- Cloud discovery uses a compact cached candidate brief, deterministic local blacklist/recycle/history/dedup filtering, then a limited deep-verification pass for the strongest candidates.
- Cloud company/freshness research is grounded directly where possible; stable company/domain research is cached for seven days.
- OpenRouter is a first-class provider with model routing, tests, server-side web-search/web-fetch support where available, token/search usage accounting and reported-cost tracking.

## Cloud AI cost guardrails

Search Sources → Schedule is renamed **Schedule / Limits** and separates normal scheduling, Local GPU / Source-Guided limits and Cloud AI limits. Conservative defaults include 4 automatic cloud campaign runs/day, 6-hour minimum cloud interval, 20 cloud requests/run, 50 native searches/run, 20 discovery candidates, 10 deep-research candidates, 120 cloud requests/day, 200 web searches/day, 500k input tokens/day, 75k output+reasoning tokens/day, 10 passive enrichments/day and 5 page-view recoveries/day. OpenRouter reported spend has a $5/day default cap.

Cloud budget checks are atomic across workers. Cloud fallback consumes Cloud AI capacity. Diagnostics, Performance Lab and manual actions do not silently bypass Cloud AI limits. Test Discovery may still bypass only the ordinary search-provider daily request limit for diagnostics; a Cloud limit produces **Not Executed — Limit Reached**, not zero results or a provider-health failure.

## AI readiness and no-GPU portal operation

- Authentication, dashboard, existing records, configuration, history, recycle/blacklist and Resource Usage remain available without a GPU and on non-macOS hosts.
- New campaign runs require either a usable Local GPU/Ollama route or a successfully validated Cloud AI route.
- Dashboard, top-right status and AI & Discovery show actionable readiness information.
- Core restart/smoke health is independent of Ollama/GPU readiness, so cloud-only/no-GPU deployments can remain healthy.

## One-shot enrichment and manual refresh

Opportunity/Hidden Lead summaries, company research and freshness follow an evidence-generation lifecycle: one initial automatic attempt, one page-view recovery attempt when needed, and no timed/scheduler retry loop. Materially changed evidence starts a new generation. Budget skips are distinct from provider failures. Manual refresh icons allow explicit additional attempts while still respecting readiness and Cloud AI hard limits; failed company refreshes preserve previously valid information.

## Analytics

- Campaign detail adds **AI Token Usage** after Leads Found, sharing Hour/Day/Week/Month/date filters and explicit campaign/run attribution.
- Campaign charts draw visible Y axes and baselines.
- Resource Usage adds **Today's Cloud Usage** above Token Categories with daily request/search/token/passive/recovery gauges and OpenRouter reported cost when available.
- CPU, Memory & GPU adds Local Tokens and Cloud Tokens (input + output) over the same timeline.
- NVIDIA hosts add a VRAM usage line sourced from `nvidia-smi`/NVML. macOS omits the VRAM line because Apple uses unified memory.

## Ubuntu / NVIDIA

`initial_setup.sh` now dispatches to macOS or Ubuntu setup. `SCOUTBOX_AI_RUNTIME=auto` is the default and selects the NVIDIA Compose override on Linux when `nvidia-smi` is available. It may be set in `.env` or the shell to `nvidia`, `cpu`, or `external/cloud`. Restart and smoke helpers use the same profile selector.

## UI refinements

- Campaign sidebar running badge removed.
- Blacklist Scope and Recycle Bin Item Type are larger icon-only cells with tooltips/accessibility labels.
- Recycle Bin retention/suppression notice moved above the toolbar and enlarged slightly.
- Test Discovery opens directly; confirmation remains on Run Test.

## Schema and upgrade

Migration `0032_v0844_cloud_limits_openrouter_nvidia.py` adds Cloud AI limit settings and counters, OpenRouter choice, enrichment lifecycle JSON state, reusable company research cache, and NVIDIA VRAM sample fields. Keep the existing `.env` and Docker volumes and run `./restart_scout_box.sh`; Django applies migrations during the normal container startup path.
