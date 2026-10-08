#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
die(){ printf '\nERROR: %s\n' "$*" >&2; exit 1; }; info(){ printf '\n==> %s\n' "$*"; }; warn(){ printf '\nWARNING: %s\n' "$*" >&2; }
[[ -f docker-compose.yml && -f .env.example ]] || die "Run this from the extracted ScoutBox root."
command -v docker >/dev/null 2>&1 || die "Docker is required. Install Docker Engine and the Compose v2 plugin first."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is unavailable."
docker info >/dev/null 2>&1 || die "Docker daemon is not running or the current user cannot access it."
command -v python3 >/dev/null 2>&1 || die "python3 is required for secure first-run configuration."
NEW_ENV=0; ADMIN_PASSWORD_GENERATED=""
if [[ ! -f .env ]]; then
  info "Creating secure .env"
  cp .env.example .env; chmod 600 .env; NEW_ENV=1
  DJANGO_SECRET_KEY="$(openssl rand -hex 48)"; POSTGRES_PASSWORD="$(openssl rand -base64 36 | tr -d '\n' | tr '/+' '_-' | cut -c1-42)"; ADMIN_PASSWORD_GENERATED="$(openssl rand -base64 30 | tr -d '\n' | tr '/+' '_-' | cut -c1-32)"
  FERNET_KEY="$(python3 - <<'PY'
import base64,secrets
print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
PY
)"
  python3 - "$DJANGO_SECRET_KEY" "$POSTGRES_PASSWORD" "$ADMIN_PASSWORD_GENERATED" "$FERNET_KEY" <<'PY'
from pathlib import Path
import sys
p=Path('.env'); vals={'DJANGO_SECRET_KEY':sys.argv[1],'POSTGRES_PASSWORD':sys.argv[2],'PORTAL_ADMIN_PASSWORD':sys.argv[3],'PORTAL_FERNET_KEY':sys.argv[4]}; out=[]; seen=set()
for line in p.read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k=line.split('=',1)[0]
        if k in vals: out.append(f'{k}={vals[k]}');seen.add(k);continue
    out.append(line)
for k,v in vals.items():
    if k not in seen: out.append(f'{k}={v}')
p.write_text('\n'.join(out)+'\n')
PY
else
  chmod 600 .env 2>/dev/null || true; info "Existing .env found; preserving it unchanged."
fi
source "$ROOT/scripts/compose_profile.sh"
info "Selected AI runtime profile: $SCOUTBOX_EFFECTIVE_RUNTIME"
if [[ "$SCOUTBOX_EFFECTIVE_RUNTIME" == "nvidia" ]]; then
  nvidia-smi -L >/dev/null 2>&1 || warn "nvidia-smi is not usable; portal can still run, but local GPU AI may not be ready."
fi
dc config >/dev/null || die "Compose configuration is invalid."
chmod +x restart_scout_box.sh initial_setup.sh initial_setup_ubuntu.sh scripts/*.sh 2>/dev/null || true
bash ./scripts/start_host_telemetry.sh >/dev/null 2>&1 || true
info "Building and starting ScoutBox"
dc up -d --build
info "Waiting for portal health"
ready=0
for _ in $(seq 1 90); do cid="$(dc ps -q web 2>/dev/null || true)"; [[ -n "$cid" ]] || { sleep 2; continue; }; st="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"; if [[ "$st" == "healthy" ]]; then ready=1; break; fi; [[ "$st" == "unhealthy" ]] && break; sleep 2; done
if [[ "$ready" -ne 1 ]]; then dc logs --tail=200 web || true; die "ScoutBox web did not become healthy."; fi
SCOUTBOX_AI_RUNTIME="$SCOUTBOX_EFFECTIVE_RUNTIME" ./scripts/smoke.sh || die "Core smoke checks failed."
PORT="$(awk -F= '/^PORTAL_HOST_PORT=/{print $2;exit}' .env)"; PORT="${PORT:-80}"
printf '\nScoutBox is ready: http://localhost:%s/\n' "$PORT"
if [[ "$NEW_ENV" -eq 1 ]]; then printf 'Admin email: %s\nAdmin password: %s\n' "$(awk -F= '/^PORTAL_ADMIN_EMAIL=/{print $2;exit}' .env)" "$ADMIN_PASSWORD_GENERATED"; fi
printf 'Runtime profile: %s\n' "$SCOUTBOX_EFFECTIVE_RUNTIME"
printf 'For upgrades, preserve .env and run ./restart_scout_box.sh\n'
