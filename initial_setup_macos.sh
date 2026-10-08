#!/usr/bin/env bash
set -euo pipefail

# ScoutBox — macOS / Apple Silicon initial bootstrap
# Place this script in the extracted ScoutBox release directory and run:
#   chmod +x initial_setup_macos.sh
#   ./initial_setup_macos.sh
#
# This script intentionally does NOT store ToughDev MySQL credentials in .env.
# Enter those later in:
#   ScoutBox -> System Configuration -> ToughDev blog statistics

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || true)"
[[ -n "$VERSION" ]] || VERSION="unknown"

die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }

[[ -f docker-compose.yml ]] || die "Run this from the extracted ScoutBox root (docker-compose.yml not found)."
[[ -f .env.example ]] || die ".env.example not found."

command -v docker >/dev/null 2>&1 || die "Docker CLI not found. Install/start Docker Desktop for Mac first."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is not available."

if ! docker info >/dev/null 2>&1; then
    if [[ -d /Applications/Docker.app ]]; then
        info "Docker Desktop is installed but the daemon is not ready. Opening Docker Desktop..."
        open -a Docker || true
        printf "Waiting for Docker"
        for _ in $(seq 1 90); do
            if docker info >/dev/null 2>&1; then
                printf " ready.\n"
                break
            fi
            printf "."
            sleep 2
        done
        docker info >/dev/null 2>&1 || die "Docker Desktop did not become ready."
    else
        die "Docker daemon is not running."
    fi
fi

# ScoutBox defaults to host port 80 for compatibility with existing installations.
# The value lives in .env and can be changed safely with ./set_port.sh PORT if
# another local web service already owns port 80.
PORTAL_HOST_PORT="$(awk -F= '/^PORTAL_HOST_PORT=/{print $2; exit}' .env 2>/dev/null || true)"
PORTAL_HOST_PORT="${PORTAL_HOST_PORT:-80}"
if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORTAL_HOST_PORT" -sTCP:LISTEN 2>/dev/null | grep -q .; then
    warn "TCP port $PORTAL_HOST_PORT is already in use:"
    lsof -nP -iTCP:"$PORTAL_HOST_PORT" -sTCP:LISTEN 2>/dev/null || true
    warn "Choose another port with ./set_port.sh PORT before starting ScoutBox."
fi

NEW_ENV=0
ADMIN_PASSWORD_GENERATED=""

if [[ ! -f .env ]]; then
    info "Creating .env from .env.example"
    cp .env.example .env
    chmod 600 .env
    NEW_ENV=1

    command -v python3 >/dev/null 2>&1 || die "python3 is required to generate secure configuration values."

    DJANGO_SECRET_KEY="$(openssl rand -hex 48)"
    POSTGRES_PASSWORD="$(openssl rand -base64 36 | tr -d '\n' | tr '/+' '_-' | cut -c1-42)"
    ADMIN_PASSWORD_GENERATED="$(openssl rand -base64 30 | tr -d '\n' | tr '/+' '_-' | cut -c1-32)"
    FERNET_KEY="$(python3 - <<'PY'
import base64, secrets
print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
PY
)"

    # BSD/GNU-sed-independent editing.
    python3 - "$DJANGO_SECRET_KEY" "$POSTGRES_PASSWORD" "$ADMIN_PASSWORD_GENERATED" "$FERNET_KEY" <<'PY'
from pathlib import Path
import sys

path = Path(".env")
values = {
    "DJANGO_SECRET_KEY": sys.argv[1],
    "POSTGRES_PASSWORD": sys.argv[2],
    "PORTAL_ADMIN_PASSWORD": sys.argv[3],
    "PORTAL_FERNET_KEY": sys.argv[4],
}
lines = path.read_text().splitlines()
seen = set()
out = []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0]
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n")
PY

    info "Secure local secrets were generated in .env (permissions 600)."
else
    info "Existing .env found; leaving all existing secrets/settings unchanged."
    chmod 600 .env || true
fi

# Optional LAN access: add the Mac's current Wi-Fi/Ethernet address to ALLOWED_HOSTS.
LAN_IP=""
for iface in en0 en1; do
    candidate="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [[ -n "$candidate" ]]; then
        LAN_IP="$candidate"
        break
    fi
done

if [[ -n "$LAN_IP" ]]; then
    printf '\nDetected Mac LAN address: %s\n' "$LAN_IP"
    read -r -p "Allow access to ScoutBox via this LAN IP? [y/N] " ans
    if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
        python3 - "$LAN_IP" <<'PY'
from pathlib import Path
import sys

ip = sys.argv[1]
p = Path(".env")
lines = p.read_text().splitlines()
out = []
done = False
for line in lines:
    if line.startswith("DJANGO_ALLOWED_HOSTS="):
        hosts = [x.strip() for x in line.split("=",1)[1].split(",") if x.strip()]
        if ip not in hosts:
            hosts.append(ip)
        line = "DJANGO_ALLOWED_HOSTS=" + ",".join(hosts)
        done = True
    out.append(line)
if not done:
    out.append(f"DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],host.docker.internal,{ip}")
p.write_text("\n".join(out) + "\n")
PY
        info "Added ${LAN_IP} to DJANGO_ALLOWED_HOSTS."
    fi
fi

# Make supplied helpers executable in case archive/file transfer permissions were lost.
chmod +x entrypoint.sh restart_scout_box.sh set_port.sh scripts/smoke.sh reset_admin_password.sh reset_mail_defaults.sh print_creds.sh 2>/dev/null || true

info "Checking host-native Ollama"
if command -v ollama >/dev/null 2>&1; then
    if curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        printf "Ollama API is reachable at http://127.0.0.1:11434\n"
        ollama list || true
    else
        warn "Ollama is installed but its API is not reachable at 127.0.0.1:11434."
        warn "Start the Ollama app/service before configuring local AI in ScoutBox."
    fi
else
    warn "Ollama is not installed. ScoutBox itself can still run, but Local AI will be unavailable."
fi

info "Validating Docker Compose configuration"
docker compose config >/dev/null

info "Building and starting ScoutBox"
# Best-effort host telemetry bridge; failure never blocks ScoutBox startup.
bash ./scripts/start_host_telemetry.sh >/dev/null 2>&1 || true

docker compose up -d --build

PORTAL_HOST_PORT="$(awk -F= '/^PORTAL_HOST_PORT=/{print $2; exit}' .env 2>/dev/null || true)"
PORTAL_HOST_PORT="${PORTAL_HOST_PORT:-80}"
info "Waiting for http://localhost:${PORTAL_HOST_PORT}/login/"
READY=0
for _ in $(seq 1 90); do
    if curl -fsS --max-time 3 "http://localhost:${PORTAL_HOST_PORT}/login/" >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 2
done

if [[ "$READY" -ne 1 ]]; then
    warn "Portal did not become reachable within the expected time."
    docker compose ps || true
    warn "Inspect: docker compose logs --tail=200 web worker telemetry_sampler discovery_worker forum_worker beat"
    exit 1
fi

info "ScoutBox is reachable"
docker compose ps

info "Running ScoutBox smoke test"
if ./scripts/smoke.sh; then
    info "Smoke test completed."
else
    warn "One or more smoke checks failed. The portal may still be usable; inspect the reported component."
fi

printf '\n============================================================\n'
printf 'ScoutBox v%s is up\n' "$VERSION"
printf 'Portal:       http://localhost:%s/\n' "$PORTAL_HOST_PORT"
printf 'Mailpit UI:   http://localhost:8025/\n'
if [[ -n "$LAN_IP" ]]; then
    printf 'Mac LAN IP:   %s\n' "$LAN_IP"
fi
printf 'Admin email:  %s\n' "$(grep '^PORTAL_ADMIN_EMAIL=' .env | cut -d= -f2-)"
if [[ -n "$ADMIN_PASSWORD_GENERATED" ]]; then
    printf 'Admin password generated for this new install:\n  %s\n' "$ADMIN_PASSWORD_GENERATED"
    printf 'Store it now. Django will later retain only its password hash.\n'
else
    printf 'Admin password: existing .env/database value was not changed.\n'
fi
printf '\nNext web setup:\n'
printf '  1. Email -> Email Configuration\n'
printf '  2. AI / Usage -> Providers & routing\n'
printf '  3. Profile -> upload CVs and set preferences\n'
printf '  4. Search Scope / Sources / Targeted Campaigns\n'
printf '  5. System Configuration -> ToughDev blog statistics\n'
printf '\nMySQL tracking credentials DO NOT belong in .env.\n'
printf 'Enter them through System Configuration so ScoutBox encrypts them in PostgreSQL.\n'
printf '============================================================\n'
