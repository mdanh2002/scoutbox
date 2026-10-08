#!/usr/bin/env bash
set -euo pipefail

# ScoutBox upgrade/restart helper.
# Use this AFTER the initial installation when application files have been
# replaced by a newer ScoutBox release.
#
# Important safety properties:
#   * requires the existing .env -- never creates or regenerates secrets
#   * never removes Docker volumes
#   * preserves PostgreSQL/Redis/Mailpit/media data
#   * rebuilds application images and runs the normal web bootstrap/migrations
#   * detects a persistent-PostgreSQL password mismatch and synchronizes the
#     local ScoutBox database role to the password already present in .env
#
# For a brand-new installation use ./initial_setup.sh instead.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Auto-select Ubuntu/NVIDIA, CPU-local, or host/cloud AI without changing application code.
source "$ROOT/scripts/compose_profile.sh"

info() { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ -f docker-compose.yml ]] || die "docker-compose.yml not found. Run this from the ScoutBox root directory."
[[ -f .env ]] || die ".env is missing. Upgrade restart REFUSES to generate a new one. Restore/copy your previous .env, then run this script again. For a truly new install use ./initial_setup.sh."
chmod 600 .env 2>/dev/null || true

command -v docker >/dev/null 2>&1 || die "Docker CLI not found."
dc version >/dev/null 2>&1 || die "Docker Compose v2 is not available."
docker info >/dev/null 2>&1 || die "Docker Desktop/daemon is not running."

# Validate before stopping the currently running installation.
info "Validating Compose configuration with the existing .env"
dc config >/dev/null

VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || true)"
[[ -n "$VERSION" ]] || VERSION="unknown"
printf 'ScoutBox version in this source tree: %s\n' "$VERSION"
printf 'Using existing environment file: %s/.env\n' "$ROOT"
printf 'AI runtime profile: %s\n' "$SCOUTBOX_EFFECTIVE_RUNTIME"

# Keep a local safety copy of the exact environment used for this restart.
# This is deliberately outside the Docker volumes and contains secrets, so it
# is mode 600 and is never printed.
ENV_BACKUP=".env.upgrade-backup"
cp -p .env "$ENV_BACKUP"
chmod 600 "$ENV_BACKUP" 2>/dev/null || true
printf 'Environment safety copy: %s/%s\n' "$ROOT" "$ENV_BACKUP"

# VERSION is the single source of truth for the application release. Older
# ScoutBox releases stored PORTAL_VERSION in .env; remove only that deprecated
# non-secret key during upgrade. All credentials and every other setting remain
# exactly as supplied in the preserved .env (the pre-edit copy is above).
if grep -q '^PORTAL_VERSION=' .env 2>/dev/null; then
    ENV_TMP=".env.version-clean.$$"
    awk '!/^PORTAL_VERSION=/' .env > "$ENV_TMP"
    chmod 600 "$ENV_TMP" 2>/dev/null || true
    mv "$ENV_TMP" .env
    printf 'Removed deprecated PORTAL_VERSION from .env; VERSION now controls the release number.\n'
fi

info "Stopping ScoutBox containers without deleting volumes"
dc down --remove-orphans

info "Rebuilding ScoutBox application images"
# Build the mandatory ScoutBox application images explicitly.  The optional
# External Statistics sidecar has its own build context and may be removed from
# public/community bundles; a missing optional context must never prevent a
# normal ScoutBox upgrade/restart.
dc build web worker telemetry_sampler discovery_worker forum_worker beat

STATS_SERVICE_BUILD_OK=0
if [[ -d "$ROOT/stats_service" && -f "$ROOT/stats_service/Dockerfile" ]]; then
    info "Building optional External Statistics service"
    if dc build stats_service; then
        STATS_SERVICE_BUILD_OK=1
    else
        warn "External Statistics service could not be built. ScoutBox will continue without external click-statistics synchronization."
    fi
else
    warn "External Statistics sidecar is not included in this bundle. ScoutBox will continue normally without it."
fi

# Bring up infrastructure first. This gives us a chance to verify the current
# .env against the persistent database before Django starts retrying.
info "Starting persistent infrastructure services"
# Best-effort host telemetry bridge; failure never blocks ScoutBox startup.
bash ./scripts/start_host_telemetry.sh >/dev/null 2>&1 || true

dc up -d db redis mailpit greenmail

info "Waiting for PostgreSQL health"
DB_READY=0
for _ in $(seq 1 60); do
    status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$(dc ps -q db)" 2>/dev/null || true)"
    if [[ "$status" == "healthy" ]]; then
        DB_READY=1
        break
    fi
    sleep 2
done
[[ "$DB_READY" -eq 1 ]] || {
    dc ps || true
    dc logs --tail=100 db || true
    die "PostgreSQL did not become healthy."
}

# A Docker PostgreSQL volume keeps the password that was set when the database
# was first initialized. POSTGRES_PASSWORD in a newly generated .env would NOT
# alter that existing role. This script never regenerates .env, but it also
# detects an already-existing mismatch (for example after an earlier accidental
# regeneration) and aligns the local ScoutBox role to the password in .env.
info "Verifying the current .env PostgreSQL credential against the persistent database"
if dc exec -T db sh -lc \
    'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT 1"' \
    >/dev/null 2>&1; then
    printf 'PostgreSQL authentication matches the existing .env.\n'
else
    warn "The PostgreSQL volume password does not match the existing .env."
    warn "Synchronizing the LOCAL ScoutBox PostgreSQL role to the password already stored in .env; no data or volumes will be removed."

    if ! dc exec -T db sh -lc \
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v role="$POSTGRES_USER" -v pw="$POSTGRES_PASSWORD"' <<'SQL'
SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'role', :'pw') \gexec
SQL
    then
        die "Could not synchronize the PostgreSQL role password. The database has not been deleted. Restore the previous .env or repair the role manually."
    fi

    if ! dc exec -T db sh -lc \
        'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT 1"' \
        >/dev/null 2>&1; then
        die "PostgreSQL authentication is still failing after synchronization."
    fi
    printf 'PostgreSQL role password is now synchronized with .env.\n'
fi

info "Inspecting database bootstrap state"
if ! dc exec -T db sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<'SQL'
SELECT 'auth_user=' || CASE WHEN to_regclass('public.auth_user') IS NULL THEN 'missing' ELSE 'present' END;
SELECT 'django_migrations=' || CASE WHEN to_regclass('public.django_migrations') IS NULL THEN 'missing' ELSE 'present' END;
SELECT 'portal_settings=' || CASE WHEN to_regclass('public.portal_portalsettings') IS NULL THEN 'missing' ELSE 'present' END;
SQL
then
    warn "Could not read schema preflight status; continuing to the idempotent web bootstrap."
fi

info "Starting ScoutBox web service (legacy schema adoption + migration bootstrap)"
dc up -d web

info "Waiting for ScoutBox web health"
WEB_READY=0
for _ in $(seq 1 90); do
    cid="$(dc ps -q web 2>/dev/null || true)"
    if [[ -n "$cid" ]]; then
        status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"
        if [[ "$status" == "healthy" ]]; then
            WEB_READY=1
            break
        fi
        if [[ "$status" == "unhealthy" ]]; then
            break
        fi
    fi
    sleep 2
done

if [[ "$WEB_READY" -ne 1 ]]; then
    dc ps || true
    dc logs --no-color --tail=200 web || true
    die "ScoutBox web did not become healthy. Persistent volumes were preserved."
fi

# Start the optional sidecar only after the web bootstrap has completed. This
# also gives the one-time legacy-configuration migration a chance to create the
# private runtime configuration consumed by the sidecar. Failure is deliberately
# non-fatal: External Statistics is an optional integration.
if [[ "$STATS_SERVICE_BUILD_OK" -eq 1 ]]; then
    info "Starting optional External Statistics service"
    if ! dc up -d stats_service; then
        warn "External Statistics service could not be started. ScoutBox will continue normally without external click-statistics synchronization."
    fi
fi

info "Starting background worker, resource sampler, discovery worker, forum worker and scheduler"
dc up -d worker telemetry_sampler discovery_worker forum_worker beat

info "Current service status"
dc ps

if [[ -x ./scripts/smoke.sh ]]; then
    info "Running ScoutBox smoke test"
    if ! SCOUTBOX_AI_RUNTIME="$SCOUTBOX_EFFECTIVE_RUNTIME" ./scripts/smoke.sh; then
        warn "One or more smoke checks failed. Containers remain running; inspect the reported component."
        exit 1
    fi
fi

printf '\n============================================================\n'
printf 'ScoutBox %s restart/upgrade completed.\n' "$VERSION"
HOST_BIND="$(dc port web 8000 2>/dev/null | head -1 || true)"
PORTAL_HOST_PORT="${HOST_BIND##*:}"
PORTAL_HOST_PORT="${PORTAL_HOST_PORT:-80}"
printf 'Portal:      http://localhost:%s/\n' "$PORTAL_HOST_PORT"
printf 'Mailpit UI:  http://localhost:8025/\n'
printf '\nPreserved:\n'
printf '  .env and encryption keys\n'
printf '  PostgreSQL volume\n'
printf '  Redis volume\n'
printf '  Mailpit volume\n'
printf '  uploaded media volume\n'
printf '\nFor future upgrades: replace application files but KEEP .env, then run:\n'
printf '  ./restart_scout_box.sh\n'
printf '\nDo not use initial_setup.sh for an existing installation.\n'
printf '============================================================\n'
