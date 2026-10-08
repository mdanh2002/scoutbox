# ScoutBox 0.8.53

## Local AI readiness

ScoutBox now distinguishes unknown accelerator identity from a confirmed absence of supported acceleration. Startup always records static host OS/architecture identity even if Python is unavailable, so Apple Silicon can be recognized from Darwin + arm64. When Ollama is reachable and models exist but accelerator evidence has not yet been collected, the UI shows **Identifying local accelerator…** and automatically queues a lightweight local inference probe. Running Test Selection is no longer required for normal Local AI readiness.

Apple Silicon is accepted through host identity or automatic inference evidence without a discrete VRAM requirement. NVIDIA/Linux telemetry remains unchanged.

## Hidden Lead noise blacklist

The built-in `Hidden Leads Only` blacklist now contains a broader set of high-noise documentation, tutorial, publisher, job-board, contact-directory, social-platform and large-enterprise domains. They remain eligible as normal Opportunity/search evidence where applicable; the scope suppresses only Hidden Lead creation. Built-in entries are editable/removable from Blacklist.
