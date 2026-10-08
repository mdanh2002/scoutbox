#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo "ERROR: .env not found. Run initial_setup_macos.sh first." >&2; exit 1; }
port="${1:-}"
if [[ -z "$port" ]]; then
  read -r -p "ScoutBox host port [80]: " port
  port="${port:-80}"
fi
[[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1024 && port <= 65535 )) || { echo "ERROR: choose a TCP port from 1024 to 65535." >&2; exit 1; }
python3 - "$port" <<'PY'
from pathlib import Path
import sys
port=sys.argv[1]
p=Path('.env')
lines=p.read_text().splitlines()
out=[]; done=False
for line in lines:
    if line.startswith('PORTAL_HOST_PORT='):
        out.append(f'PORTAL_HOST_PORT={port}'); done=True
    else:
        out.append(line)
if not done:
    out.append(f'PORTAL_HOST_PORT={port}')
p.write_text('\n'.join(out)+'\n')
PY
chmod 600 .env 2>/dev/null || true
echo "ScoutBox host port set to $port in .env."
echo "Apply it with: ./restart_scout_box.sh"
