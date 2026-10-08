#!/bin/sh
set -eu

if [ "${WAIT_FOR_DB:-0}" = "1" ]; then
  echo "Waiting for PostgreSQL..."
  until nc -z "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}"; do sleep 1; done
fi

# Only the web container performs schema/bootstrap work. Workers/beat wait for
# the web bootstrap to finish via the compose healthcheck, avoiding concurrent
# migrate/seed operations on a clean database.
if [ "${BOOTSTRAP_PORTAL:-0}" = "1" ]; then
  # v0.7.3 introduces the portal app's first real migration. Older ScoutBox
  # releases created portal tables with --run-syncdb. Apply auth first so
  # auth_user exists, complete any partial legacy portal table set without
  # deleting data, then let Django adopt existing portal tables with
  # --fake-initial (or create them normally on a fresh database).
  echo "Applying Django authentication migrations..."
  python manage.py migrate auth --fake-initial --noinput

  echo "Preparing any pre-migration ScoutBox schema for safe adoption..."
  python manage.py prepare_legacy_schema

  echo "Applying Django and ScoutBox migrations..."
  python manage.py migrate --fake-initial --noinput

  # Pre-migration MVP releases added a few fields with schema_editor rather than
  # migration files. On legacy databases the initial migration is fake-applied,
  # so keep this compatibility layer to add any of those columns that are absent.
  python manage.py ensure_schema
  # Reconcile orphaned task state before the web container becomes healthy and new
  # workers begin accepting work. This clears old permanent hourglasses after restarts.
  python manage.py reconcile_worker_state || true
  python manage.py seed_defaults
  python manage.py migrate_external_stats_config || true
  python manage.py collectstatic --noinput >/dev/null
fi

if [ "${BOOTSTRAP_PORTAL:-0}" = "1" ]; then
  python manage.py log_service_event started || true
  "$@" &
  portal_child_pid=$!
  portal_shutdown=0
  trap 'portal_shutdown=1; kill -TERM "$portal_child_pid" 2>/dev/null || true' TERM INT
  set +e
  wait "$portal_child_pid"
  portal_status=$?
  set -e
  if [ "$portal_shutdown" = "1" ]; then
    python manage.py log_service_event stopped || true
  fi
  exit "$portal_status"
fi

exec "$@"
