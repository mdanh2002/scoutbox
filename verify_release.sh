#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "FAIL: $1" >&2; exit 1; }
pass(){ echo "PASS: $1"; }
VERIFY_TMP=".scoutbox-verify-011152"
mkdir -p "$VERIFY_TMP"
cleanup_verify_tmp(){ find "$VERIFY_TMP" -type f -delete 2>/dev/null || true; find "$VERIFY_TMP" -depth -type d -empty -delete 2>/dev/null || true; }
trap cleanup_verify_tmp EXIT

[[ "$(tr -d '[:space:]' < VERSION)" == "0.11.152" ]] || fail "VERSION is not 0.11.152"
[[ "$(tr -d '\r\n' < RELEASE_ID)" == "ScoutBox 0.11.152" ]] || fail "RELEASE_ID stale"
[[ "$(tr -d '\r\n' < BUILD_INFO.txt)" == "ScoutBox v0.11.152" ]] || fail "BUILD_INFO stale"
[[ "$(head -n1 README.md)" == "# ScoutBox 0.11.152" ]] || fail "README stale"
[[ -f docs/RELEASE_NOTES_0.11.152.md && -f RELEASE_POLICY.md ]] || fail "release metadata missing"
PYTHONDONTWRITEBYTECODE=1 python scripts/regression_v011152.py || fail "0.11.152 targeted regressions"
pass "0.11.152 targeted regressions"

python - <<'PY' || exit 1
import ast, pathlib, sys
bad=[]
for path in pathlib.Path('.').rglob('*.py'):
    if any(part in {'.git','__pycache__','.scoutbox-verify-011152'} for part in path.parts):
        continue
    try: ast.parse(path.read_text(encoding='utf-8'))
    except Exception as exc: bad.append((str(path),str(exc)))
if bad:
    print('Python AST failures:',bad,file=sys.stderr); sys.exit(1)
print('Python AST parse passed')
PY
pass "Python AST parse"
PYTHONPYCACHEPREFIX="$PWD/$VERIFY_TMP/pyc" python -m compileall -q . || fail "Python compileall failed"
pass "Python compileall"

python - <<'PY' || exit 1
import yaml
for name in ['docker-compose.yml','docker-compose.nvidia.yml','docker-compose.cpu-ollama.yml']:
    with open(name,encoding='utf-8') as fh: yaml.safe_load(fh)
print('Docker Compose YAML parse passed')
PY
pass "Docker Compose YAML parse"
find . -name '*.sh' -print0 | xargs -0 -n1 bash -n || fail "shell syntax failed"
pass "Shell syntax"

python - <<'PY' || exit 1
from pathlib import Path
import re
out=Path('.scoutbox-verify-011152')
for name in ('profile','stats','telemetry','settings','link_rules','links','email_history','email_config','gpt_log','opportunities','cold_contact','sources','opportunity_detail','hidden_lead_detail'):
    text=(Path('templates/portal')/(name+'.html')).read_text(encoding='utf-8')
    marker='{% block scripts %}<script>'
    if marker not in text: continue
    start=text.index(marker)+len(marker); end=text.index('</script>{% endblock %}',start)
    script=text[start:end]
    script=re.sub(r"{%\s*url\s+[^%]+%}",'/__template_url__/',script)
    script=re.sub(r"{{[^{}]+}}",'0',script)
    script=re.sub(r"{%[^%]+%}",'',script)
    (out/(name+'.js')).write_text(script,encoding='utf-8')
base=Path('templates/portal/base.html').read_text(encoding='utf-8')
start=base.index('function initToolbarSelectFocusRelease()')
end=base.index("document.addEventListener('DOMContentLoaded'",start)
(out/'base-toolbar.js').write_text(base[start:end],encoding='utf-8')
PY
for script in "$VERIFY_TMP"/*.js; do node --check "$script" || fail "JavaScript syntax: $script"; done
pass "JavaScript syntax"

if grep -R --include='*.py' -nE 'AuditLog\.objects\.(filter|create)\([^\n]*(detail__|detail=)' portal/migrations >/dev/null; then
    fail "migration references removed AuditLog.detail field"
fi
pass "AuditLog migration field compatibility"

if find . -path './.scoutbox-verify-011152' -prune -o \( -path '*/__pycache__' -o -name '*.pyc' \) -print -quit | grep -q .; then fail "bytecode artifacts present"; fi
pass "No bytecode artifacts"
cleanup_verify_tmp
echo "ScoutBox 0.11.152 static release verification passed."
