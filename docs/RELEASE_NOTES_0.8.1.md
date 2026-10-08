# ScoutBox 0.8.1 release notes

0.8.1 is a major usability/workflow release built to upgrade in place from the healthy v0.7.4 installation.

## Highlights

- Grouped navigation, live menu search, breadcrumbs, Quick Start and cleaner account/version placement.
- Live Dashboard Now Running status for campaigns and automatic tasks.
- Multi-country profile/scope/campaign controls, stronger validation and compensation-period support.
- Separate CV/cover upload areas, delete-only UI and full Added timestamps.
- Search Sources redesign with live filter, Select All/Clear All, compact tags, advanced quota tuning, provider status/tests and limited public fallbacks.
- Query adapters for Google, Bing, DuckDuckGo, Brave Search, Yahoo Search, Mojeek, Startpage, Ecosia, Yandex, Baidu and Naver.
- Real campaign templates and Celery-backed campaign runs with stop/rerun/rotation preview.
- Celery-backed history/document/mail imports plus Add All/selected historical application actions.
- Applied Role edit/delete and manual Prepared Application creation.
- XLSX list exports.
- Email profile dropdown/active state, full-body email modal and contact phone field.
- Company & Role Research naming/description.
- Automatic article-aware ToughDev link personalization.
- Ollama prompt test, model selectors, simplified AI descriptions and UI Test Discovery.
- Portal-wide chatbot context plus live user opportunities/applications/campaign information.
- Performance Lab job-post age analysis with evidence and reasoning.

## Upgrade

Preserve `.env` and Docker volumes, replace application files, then run:

```bash
./restart_scout_box.sh
```

Do not rerun initial setup for an existing installation.

## Data/schema changes

Migration `0002_v080_workflow_ux` adds multi-location/profile/campaign fields, campaign templates/runs, automatic task records, Facebook Page records and contact phone support. Migration `0003_v081_search_and_lab` activates the expanded search-adapter set and adds Performance Lab age analysis.

No migration intentionally deletes existing opportunity/application/profile/email data.
