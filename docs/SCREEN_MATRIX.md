# v4 mockup + later requirements -> ScoutBox v0.8.1 implementation matrix

| Mockup screen | ScoutBox v0.8.1 route / function |
|---|---|
| 01 Home dashboard | `/` — daily queue, activity, health, background pause/resume |
| 02 Profile, CV & preferences | `/profile/` — multiple CV/cover assets, three free-text priority fields, live CV-derived search profile |
| 03 Search scope & ranking | `/scope/` — location, engagement/company/process/pay policy |
| 04 Source catalog | `/sources/` — broad presets, search/filter, provider budgets, Facebook settings |
| 05 Targeted campaign builder | `/campaigns/` — CV-first automatic campaign plus optional role/technology steering |
| 06 Campaign results | `/campaigns/<id>/` — live generated-query preview and raw-hit consolidation summary |
| 07 Opportunities list | `/opportunities/` — common filters/export |
| 08 Opportunity detail | `/opportunities/<id>/` — evidence, age reasoning, enrichment, prepare action |
| 09 Company/role intelligence | `/companies/` |
| 10 Applied import & suppression | `/imports/` — DOCX/PDF/XLSX/TXT/CSV with dedicated Status/Outcome and Notes |
| 11 Applied roles | `/applied/` |
| 12 Prepared applications | `/applications/` |
| 13 Email application editor | `/applications/<id>/edit/` — HTML/plain editor, model comparison, draft lifecycle |
| 14 Website/ATS application pack | same application editor — role-specific Q&A drafting |
| 15 Email configuration | `/email-config/` — Internal/External persistent profiles, tests/folder mapping |
| 16 Email history/status | `/email-history/` plus `/contacts/` |
| 17 Tracking link rules | `/links/rules/` |
| 18 Tracking links registry | `/links/` |
| 19 AI providers/model routing | `/ai/` — Ollama/cloud, stage routing, dedicated chatbot Local/Cloud + model + token cap, diagnostic Test Run |
| 20 Usage/resource telemetry | `/telemetry/` plus `/health/` |
| 21 Statistics/funnel | `/stats/` |
| 22 Cold contact/hidden market | `/cold-contact/` — separate high-signal scan and draft preparation |
| 23 Audit log | `/audit/` — includes sent-mail observations and safety verification |
| 24 Users/notifications/health | `/settings/` and `/health/` |
| Added Performance Lab | `/performance/` — isolated AI/search/scrape/document benchmark/playground |

| Added site-wide chatbot | Floating **Ask ScoutBox** control on every authenticated page; read-only portal Q&A with contextual page links |
