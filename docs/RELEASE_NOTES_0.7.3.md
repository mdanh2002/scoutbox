# v0.7.3 release notes

- Fixes startup/restart failure: `django.db.utils.ProgrammingError: relation "auth_user" does not exist`.
- Root cause: the pre-v0.7.3 `portal` app had no migration files but contained a `ForeignKey` to Django `auth.User`; using `migrate --run-syncdb` for that cross-app relationship is unsupported and can attempt portal schema creation before the auth table is available.
- Adds `portal/migrations/0001_initial.py` with an explicit `AUTH_USER_MODEL` migration dependency. Fresh databases now use normal Django migration ordering.
- Existing pre-migration ScoutBox databases are adopted with `migrate --fake-initial`, preserving their existing portal tables and data.
- Adds `prepare_legacy_schema`, a compatibility preflight that completes missing legacy portal model tables and auto-created ManyToMany join tables before adoption. It never drops or truncates tables.
- `ensure_schema` remains after migration adoption to add the small set of backward-compatible columns used by earlier MVP releases when those columns are missing.
- `restart_scout_box.sh` preserves `.env`, PostgreSQL, Redis, Mailpit and media volumes and never uses `docker compose down -v`.
- `VERSION` is now the single source of truth for the installed portal release. `PORTAL_VERSION` has been removed from `.env.example`, Django reads `VERSION` directly, and upgrade restart removes only the obsolete `PORTAL_VERSION=` line from older `.env` files. Credentials and all other settings remain untouched.
- `initial_setup_macos.sh` restores execute permission on `restart_scout_box.sh` when archive permissions are lost and reads the displayed release number from `VERSION`.
- No user-facing portal workflow changes are introduced by this patch.
