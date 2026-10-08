# ScoutBox

A self-hosted web application that finds niche engineering vacancies and companies worth contacting. A candidate profile and a set of narrow campaigns steer searches across public web engines, job boards, ATS career pages, engineering forums, social sources and SearchApi. Everything that comes back is fetched, assessed by a local or cloud LLM, and filed as an **Opportunity** (a concrete vacancy), a **Hidden Lead** (a company with relevant activity but no advertised role), an **Address Book** contact or a **Facebook Page**.

## Features

- 160+ configurable search sources in 13 categories, plus 57 engineering forums and mailing lists
- SearchApi Google Jobs, Web, Forums, News and Local engines with per-market steering
- Campaigns with their own focus, markets, schedule and source selection
- Local AI through Ollama (Qwen, Gemma, …) and cloud AI through OpenAI, Gemini or OpenRouter, selectable per stage with fallback models
- Fit scoring, post-age detection, company research with RDAP domain age, role-location resolution and re-evaluation with full history
- Applications and outreach: email drafts, resume and cover-letter tailoring, application answers, IMAP drafts, tracking links
- Chatbot over the stored records, Search Activity and AI Requests logs, resource usage, diagnostics and a redacted diagnostic export for LLM analysis

## Requirements

- Docker and Docker Compose
- One of:
  - macOS with an M-series chip (Ollama on the host via Metal)
  - Linux with an NVIDIA GPU (Ollama in a container)
  - Any machine without a GPU, provided a cloud LLM provider is configured

## Quick start

1. Copy `.env.example` to `.env` — the defaults are enough for a first run.
2. Run the setup script for your machine:
   ```bash
   ./initial_setup_macos.sh     # MacBook: Docker Desktop + host Ollama
   ./initial_setup_ubuntu.sh    # Ubuntu with an NVIDIA GPU
   ```
3. Open the portal at <http://localhost:8989/>.
4. Upload a resume under **Candidate Profile**, let it populate the search profile, then create a campaign or two from the generated templates.
5. Optionally enter a SearchApi key and cloud provider keys under **Configuration › Search Sources** and **Configuration › AI & Discovery**.

Without a local or cloud model the portal starts in read-only mode and shows stored records without running new campaigns.

## Layout

```
docker-compose.yml              web, database, queue and workers
docker-compose.nvidia.yml       NVIDIA GPU overlay
initial_setup_macos.sh          Mac first setup
initial_setup_ubuntu.sh         Ubuntu first setup
opportunity_portal/             Django configuration and Celery app
portal/                         models, views, tasks and services
portal/services/search.py       search providers, including SearchApi
portal/services/ai.py           local and cloud model routing
portal/services/diagnostics.py  health and support export
templates/portal/, portal/static/
scripts/                        setup helpers
docs/                           release notes
```

## Troubleshooting

```bash
docker compose ps
docker compose exec web python manage.py check
docker compose exec web python manage.py showmigrations portal
docker compose exec web celery -A opportunity_portal inspect active --timeout 3
```

The **About** page inside the portal lists further ScoutBox-specific inspection commands, and **Configuration › Maintenance** exports a redacted diagnostic ZIP that can be handed to an LLM for analysis.

## Links

| | |
|---|---|
| SearchApi docs | <https://www.searchapi.io/docs/google-jobs> |
| Ollama API | <https://docs.ollama.com/api> |
| OpenAI API | <https://platform.openai.com/docs/api-reference> |
| Gemini API | <https://ai.google.dev/gemini-api/docs> |
| OpenRouter API | <https://openrouter.ai/docs> |

## License

To be announced with the public release.
