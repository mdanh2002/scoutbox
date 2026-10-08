#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

cat >&2 <<'WARN'
WARNING: print_creds.sh prints DECRYPTED passwords, API keys, Facebook tokens/cookies,
and other live connector secrets to the terminal. Do not run it in a shared terminal,
CI log, screen recording, support session, or shell whose output is being captured.
WARN

EXTRA_ARG=""
if [[ "${1:-}" == "--include-infrastructure" ]]; then
  EXTRA_ARG="--include-infrastructure"
elif [[ $# -gt 0 ]]; then
  echo "Usage: ./print_creds.sh [--include-infrastructure]" >&2
  exit 2
fi

if docker compose ps --status running --services 2>/dev/null | grep -qx web; then
  if [[ -n "$EXTRA_ARG" ]]; then
    docker compose exec -T web python manage.py print_creds "$EXTRA_ARG"
  else
    docker compose exec -T web python manage.py print_creds
  fi
else
  echo "web container is not running; using a one-off web container." >&2
  if [[ -n "$EXTRA_ARG" ]]; then
    docker compose run --rm -e BOOTSTRAP_PORTAL=0 web python manage.py print_creds "$EXTRA_ARG"
  else
    docker compose run --rm -e BOOTSTRAP_PORTAL=0 web python manage.py print_creds
  fi
fi
