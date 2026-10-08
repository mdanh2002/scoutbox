# v0.7.2 release notes

- Upgrade-safety patch over v0.7.1; ScoutBox application behavior is otherwise unchanged.
- Adds root `restart_scout_box.sh` for existing installations after replacing/upgrading source files.
- The restart helper requires the existing `.env` and will never generate or replace secrets.
- Docker volumes are preserved; the script never uses `docker compose down -v`.
- Rebuilds images, starts infrastructure first, verifies PostgreSQL authentication, runs the normal web migrations/bootstrap, then starts worker and beat.
- If an earlier accidental `.env` regeneration left the persistent local PostgreSQL role with the old password, the helper detects the mismatch and aligns that local role to the password already present in `.env` without deleting the database.
- `initial_setup_macos.sh` remains the initial/fresh-install bootstrap; its behavior is unchanged apart from the displayed release number.
- Retains the v0.7.1 abstract-Django-model admin registration fix.
