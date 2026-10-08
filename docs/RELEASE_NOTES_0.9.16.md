# ScoutBox 0.9.16

## Chatbot settings
- Shortens the Primary/Secondary route help text without changing routing behavior.

## About ScoutBox
- Adds a two-column **Database Info** section beneath Troubleshooting Tips.
- Summarizes the main `portal_*` PostgreSQL tables and their corresponding ScoutBox objects.
- Adds read-oriented `psql` examples plus full `pg_dump` / `pg_restore` backup and restore commands.
- Database commands resolve the active PostgreSQL database/user from the container environment, so customized `.env` values are respected.
- Restore guidance explicitly warns to stop application/worker services before replacing current database contents.

No database migration is required.
