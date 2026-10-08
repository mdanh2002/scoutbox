# ScoutBox 0.10.71

- Keeps campaign heartbeat fresh while Forum/direct-source adapters are browsing so long forum passes do not appear stalled or block the scheduler.
- Releases already-stale Forum browsing runs during upgrade.
- Restores the ScoutBox Chat export button by wiring the client-side DOCX export call to the existing chatbot export endpoint.
- Changes the About ScoutBox Discovery Mode icon so it does not duplicate the What it does icon on the same page.
- Expands CV technology extraction with explicit terms such as .NET, C#, VoIP, Asterisk, SIP/PBX and other software/embedded/network technologies.
- Rotates direct-source and local source-guided search terms across the full CV-derived technology list, including lower-frequency terms, instead of repeatedly using only the highest-scoring keywords.
