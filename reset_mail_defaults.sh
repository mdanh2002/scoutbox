#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Resetting mail configuration to Internal Development (GreenMail + Mailpit)..."
if docker compose ps --status running --services 2>/dev/null | grep -qx web; then
  docker compose exec -T web python manage.py reset_mail_defaults
else
  echo "web container is not running; using a one-off web container."
  docker compose run --rm -e BOOTSTRAP_PORTAL=0 web python manage.py reset_mail_defaults
fi

echo "Mailpit UI: http://localhost:8025/"
echo "GreenMail development IMAP is mapped to localhost:3143 for diagnostics."
