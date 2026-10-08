# ScoutBox 0.11.3

Focus label evidence repair.

- Rejects Focus labels whose specific concept tokens are not supported by record-local content.
- Prevents broad companion words such as "computing" or "infrastructure" from justifying specific labels like "Retro Computing" or "AI Infrastructure" when the actual Retro/AI evidence is absent.
- Adds stronger company/contact namespace candidates for Linux systems, systems software, low-level systems, BSPs, and Linux networking.
- Validates Local AI batch Focus assignments with the same deterministic support check before persisting.
- Queues a post-health Dashboard Activity job: `Repair Focus label evidence for 0.11.3`.
- Migration only marks the repair pending; it does not run Local AI, fetch pages, or rebuild Focus during startup.
