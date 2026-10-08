# v0.7.4 release notes

## Shell/dotenv startup helper repair

- Fixes `Opportunity: command not found` (and similar `ToughDev`, `Admin`, or `Portal` errors) emitted by `scripts/smoke.sh`.
- Root cause: the smoke helper sourced `.env` as Bash even though ScoutBox uses Docker Compose dotenv syntax. Unquoted values containing spaces are valid Compose dotenv values but are not valid shell assignment statements when sourced.
- `scripts/smoke.sh` no longer sources or executes `.env`.
- The Mailpit authenticated smoke check now runs inside the already-configured `web` container, where Docker Compose has safely parsed `.env` and supplied the environment variables.
- Credentials and deployment settings remain in `.env`; the standalone `VERSION` file remains the only source of the portal release number.

## Carried forward from v0.7.3

- Real Django `portal` initial migration with explicit auth-user dependency.
- Non-destructive legacy schema adoption for installations created by older `--run-syncdb` releases.
- Persistent PostgreSQL/Redis/Mailpit/media volumes remain preserved during restart/upgrade.
