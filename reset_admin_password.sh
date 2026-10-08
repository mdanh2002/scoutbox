#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Intentionally known recovery password. The administrator email is read from the
# portal container's PORTAL_ADMIN_EMAIL (default: admin@portal.test).
DEFAULT_PASSWORD="${RESET_ADMIN_DEFAULT_PASSWORD:-ChangeMe-Portal-123!}"

echo "Resetting portal administrator password to the recovery default..."
if docker compose ps --status running --services 2>/dev/null | grep -qx web; then
  docker compose exec -T web python manage.py reset_admin_password --password "$DEFAULT_PASSWORD"
else
  echo "web container is not running; using a one-off web container."
  docker compose run --rm -e BOOTSTRAP_PORTAL=0 web python manage.py reset_admin_password --password "$DEFAULT_PASSWORD"
fi
