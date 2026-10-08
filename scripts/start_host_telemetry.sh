#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/.scoutbox-runtime"; PIDFILE="$RUNTIME/host_telemetry.pid"; LOG="$RUNTIME/host_telemetry.log"
mkdir -p "$RUNTIME"
HOST_SYSTEM="$(uname -s 2>/dev/null || true)"; HOST_MACHINE="$(uname -m 2>/dev/null || true)"
printf '{"system":"%s","machine":"%s","platform":"%s %s"}\n' "$HOST_SYSTEM" "$HOST_MACHINE" "$HOST_SYSTEM" "$HOST_MACHINE" > "$RUNTIME/host_identity.json" 2>/dev/null || true
if ! command -v python3 >/dev/null 2>&1; then echo "ScoutBox: python3 unavailable; using host identity only." >&2; exit 0; fi
PYTHON_BIN="$(command -v python3)"

# Stop the legacy nohup bridge if an older ScoutBox release left it running.
if [[ -f "$PIDFILE" ]]; then
  OLD="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ "$OLD" =~ ^[0-9]+$ ]] && kill -0 "$OLD" 2>/dev/null; then kill "$OLD" 2>/dev/null || true; sleep .2; fi
  rm -f "$PIDFILE" 2>/dev/null || true
fi

# macOS: supervise the bridge with launchd. This keeps the telemetry publisher
# alive across sleep/wake and automatically restarts it if it exits. Fall back
# to the portable nohup path when launchd is unavailable (for example SSH-only
# sessions without a GUI user domain).
if [[ "$HOST_SYSTEM" == "Darwin" ]] && command -v launchctl >/dev/null 2>&1; then
  LABEL="com.toughdev.scoutbox.host-telemetry"
  UID_NUM="$(id -u)"
  DOMAIN="gui/$UID_NUM"
  PLIST_DIR="$HOME/Library/LaunchAgents"
  PLIST="$PLIST_DIR/$LABEL.plist"
  mkdir -p "$PLIST_DIR"
  export SCOUTBOX_TELEMETRY_ROOT="$ROOT" SCOUTBOX_TELEMETRY_PYTHON="$PYTHON_BIN" SCOUTBOX_TELEMETRY_LOG="$LOG" SCOUTBOX_TELEMETRY_PLIST="$PLIST"
  "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1 || true
import os, plistlib
root=os.environ['SCOUTBOX_TELEMETRY_ROOT']; py=os.environ['SCOUTBOX_TELEMETRY_PYTHON']; log=os.environ['SCOUTBOX_TELEMETRY_LOG']; path=os.environ['SCOUTBOX_TELEMETRY_PLIST']
data={
    'Label':'com.toughdev.scoutbox.host-telemetry',
    'ProgramArguments':[py,os.path.join(root,'scripts','host_telemetry.py'),'--output',os.path.join(root,'.scoutbox-runtime','host_telemetry.json'),'--interval','5','--gpu-interval','5'],
    'WorkingDirectory':root,'RunAtLoad':True,'KeepAlive':True,'ProcessType':'Background','ThrottleInterval':5,
    'StandardOutPath':log,'StandardErrorPath':log,
}
with open(path,'wb') as fh: plistlib.dump(data,fh,sort_keys=False)
PY
  launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
  if launchctl bootstrap "$DOMAIN" "$PLIST" >/dev/null 2>&1; then
    launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      # Do not trust a merely loaded LaunchAgent: verify that it actually publishes a
      # fresh bridge snapshot. A broken/stale agent was the source of GPU-only chart gaps.
      for _ in $(seq 1 10); do
        if "$PYTHON_BIN" - "$RUNTIME/host_telemetry.json" <<'PY' >/dev/null 2>&1
import json,sys,time
try:
    data=json.load(open(sys.argv[1],encoding='utf-8'))
    stamp=float(data.get('captured_at') or 0)
    raise SystemExit(0 if stamp and time.time()-stamp < 20 else 1)
except Exception:
    raise SystemExit(1)
PY
        then
          exit 0
        fi
        sleep 1
      done
      launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
    fi
  fi
fi

nohup "$PYTHON_BIN" "$ROOT/scripts/host_telemetry.py" --output "$RUNTIME/host_telemetry.json" --interval 5 --gpu-interval 5 >>"$LOG" 2>&1 &
echo $! > "$PIDFILE"
exit 0
