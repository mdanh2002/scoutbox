#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source ./scripts/compose_profile.sh
command -v docker >/dev/null || { echo "ERROR: docker is not installed or not in PATH" >&2; exit 1; }
fail=0
check(){ local label="$1"; shift; printf '%-32s ' "$label"; if "$@" >/tmp/scoutbox-smoke.out 2>/tmp/scoutbox-smoke.err; then echo OK; else echo FAIL; sed 's/^/    /' /tmp/scoutbox-smoke.err | tail -6; fail=1; fi; }
warncheck(){ local label="$1"; shift; printf '%-32s ' "$label"; if "$@" >/tmp/scoutbox-smoke.out 2>/tmp/scoutbox-smoke.err; then echo OK; else echo "WARN (AI unavailable)"; fi; }
softcheck(){ local label="$1"; shift; printf '%-32s ' "$label"; if "$@" >/tmp/scoutbox-smoke.out 2>/tmp/scoutbox-smoke.err; then echo OK; else echo "WARN"; sed 's/^/    /' /tmp/scoutbox-smoke.err | tail -4; fi; }
check "Compose services" dc ps
check "Django system check" dc exec -T web python manage.py check
HOST_BIND="$(dc port web 8000 2>/dev/null | head -1 || true)"; HOST_PORT="${HOST_BIND##*:}"; HOST_PORT="${HOST_PORT:-80}"
check "Portal HTTP /login" curl -fsS "http://127.0.0.1:${HOST_PORT}/login/"
check "Mailpit UI" dc exec -T web sh -lc 'curl -fsS -u "${MAILPIT_UI_USER:-mailpit}:${MAILPIT_UI_PASSWORD:-mailpit-demo}" http://mailpit:8025/'
check "GreenMail IMAP port" bash -c 'exec 3<>/dev/tcp/127.0.0.1/3143; head -1 <&3 | grep -qi IMAP'
check "Celery worker ping" dc exec -T web celery -A opportunity_portal inspect ping --timeout 3
check "Forum worker service" dc exec -T forum_worker python -c "print(\"forum worker ready\")"
check "Resource sampler service" dc exec -T telemetry_sampler python -c "print(\"resource sampler ready\")"
check "Resource sample freshness" dc exec -T telemetry_sampler python scripts/check_resource_telemetry.py --wait-seconds 35 --max-sample-age 60
softcheck "GPU telemetry freshness" dc exec -T telemetry_sampler python scripts/check_resource_telemetry.py --wait-seconds 5 --max-sample-age 60 --gpu
warncheck "AI runtime / Ollama" dc exec -T web python -c "import os,requests; u=os.getenv('OLLAMA_BASE_URL','http://host.docker.internal:11434').rstrip('/'); r=requests.get(u+'/api/tags',timeout=5); r.raise_for_status()"
if [[ "$SCOUTBOX_EFFECTIVE_RUNTIME" == "nvidia" ]]; then warncheck "NVIDIA host runtime" nvidia-smi -L; fi
if [[ "$fail" -ne 0 ]]; then echo "One or more CORE smoke checks failed. Run Compose logs for web/worker/telemetry_sampler/discovery_worker/forum_worker/beat/db." >&2; exit 1; fi
echo "Core smoke checks passed. AI availability is reported separately and does not block portal health."
