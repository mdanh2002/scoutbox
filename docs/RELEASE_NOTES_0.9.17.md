# ScoutBox 0.9.17

## Database Info layout and learning reference

- Replaces the cramped Database Info two-column command layout with a two-column schema map followed by a full-width SQL reference.
- Adds a **Core workflow tables** column and a **Relations, history & diagnostics** column.
- Documents the main many-to-many bridge tables used to connect Opportunities and Hidden Leads to Campaigns.
- Adds supporting/history tables for evidence, application status/files, AI Requests, Chatbot messages and resource/usage telemetry.
- SQL examples are full-width, horizontally scroll when necessary, and preserve formatting instead of wrapping long queries.
- Adds join examples showing how ScoutBox's primary records relate in PostgreSQL.
- Backup/restore commands continue to use the active PostgreSQL container environment.

No database migration is required.
