# ScoutBox 0.9.22

## AI & Discovery

- Cloud Web Discovery now exposes provider, Primary model, Failover model, input cap and output cap for every pipeline stage.
- Each Cloud stage can use a different enabled provider; Primary and Failover are enforced to the same provider within that stage.
- Cloud Auto-select is stage-aware and cost-conscious. URL discovery prefers a capable low-cost model (for example Gemini 2.5 Flash) with an economical same-provider failover (for example Flash-Lite) and live web capability verification.
- Local automatic model selection uses the smaller detected limit from system RAM and discrete GPU VRAM. Conservative defaults are 3B at roughly 8 GB, 4B at 16 GB, 7B through 32 GB and 12B above 32 GB. Manual model selection remains unrestricted.
- Cloud and Local routing tables stay responsive; long model IDs remain inside reasonably sized dropdowns.

## Chatbot

- Local Chatbot defaults increase to a 48k input budget and 5k answer-token cap. Existing old/default 28k local routes are upgraded when the Chatbot config is saved; deliberate larger manual caps are preserved.
- Primary and Secondary Chatbot routes are preflighted independently, so a Secondary route can still answer when the Primary cannot fit the full context.
- Chatbot guidance is more decisive when stored ScoutBox evidence supports a conclusion while still requiring genuine uncertainty to be stated.

## Redis learning reference

- Redis usage is now a peer section beside Terminal & SQL examples with its own Redis icon.
- The guide explains Redis's role as ScoutBox's Celery broker/result backend, the `celery` and `discovery` queues, safe read-only commands, queue depth, key inspection, task-result metadata and basic Celery envelope extraction.

## Upgrade

Migration `0074_v0922_cloud_web_stage_routes` adds `PortalSettings.cloud_web_stage_routes` and seeds all stages from the previous Cloud Web provider/Primary/Secondary selection when present. Legacy fields are retained and synchronized for compatibility.
