# v0.6.1 release notes

- Product short name remains **ScoutBox**; long name remains **Niche Opportunity Intelligence Portal**.
- Uses the selected simple symbolic ScoutBox compass/radar logo across login, sidebar, favicon and chatbot.
- Adds a site-wide authenticated **Ask ScoutBox** chatbot.
- Chatbot is read-only, restricted to portal-related questions, keeps answers brief, redacts/excludes secrets, and returns direct links to relevant ScoutBox pages.
- AI Providers & Model Routing has dedicated chatbot controls: **Local Ollama / Cloud AI**, model, optional same-class fallback, and independent answer token cap (default 450).
- Chatbot AI usage is recorded under the `chatbot` stage in normal AI telemetry.
- Existing v0.4.x/v0.5.x workflows remain otherwise unchanged.
