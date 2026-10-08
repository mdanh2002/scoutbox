from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text()

def fail(msg):
    raise SystemExit(f'FAIL: {msg}')

if read(Path('VERSION')).strip()!='0.10.75': fail('VERSION is not 0.10.75')
if read(Path('RELEASE_ID')).strip()!='ScoutBox v0.10.75': fail('RELEASE_ID stale')
if read(Path('BUILD_INFO.txt')).strip()!='ScoutBox v0.10.75': fail('BUILD_INFO stale')
if not read(Path('README.md')).startswith('# ScoutBox 0.10.75'): fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.75.md').is_file(): fail('0.10.75 release notes missing')

ai=read(Path('portal/services/ai.py'))
tasks=read(Path('portal/tasks.py'))
planner=read(Path('portal/services/queryplanner.py'))
migration=ROOT/'portal'/'migrations'/'0106_v01075_local_ai_lane_defer.py'
if not migration.is_file(): fail('0.10.75 migration missing')
if 'class LocalAILaneBusy' not in ai: fail('LocalAILaneBusy missing')
if "SCOUTBOX_LOCAL_AI_LANE_WAIT_SECONDS', '60'" not in ai: fail('local AI lane wait default not reduced')
if 'raise LocalAILaneBusy' not in ai: fail('local AI lane still fails open instead of deferring')
if 'Local AI lane wait exceeded; continuing without lane lock' in ai: fail('old fail-open lane behavior still present')
if 'local_ai_lane_busy' not in ai or 'def local_ai_lane_busy' not in ai: fail('lane busy helper missing')
if 'local_ai_lane_busy()' not in planner: fail('query planner does not skip optional LLM aliases when lane busy')
if 'except LocalAILaneBusy as exc' not in tasks: fail('campaign job does not handle lane deferral')
if 'deferred_local_ai' not in tasks: fail('deferred local AI runs not marked/ignored')
if 'min(discovery_inflight_limit,_local_discovery_capacity_limit())' not in tasks.replace(' ', ''): fail('local scheduler not capped by local AI lane capacity')
if '0106_v01075_local_ai_lane_defer' not in str(migration): pass
if 'upgrade_released_local_ai_contention' not in migration.read_text(): fail('migration does not release local AI contention rows')

env=read(Path('.env.example'))
if 'SCOUTBOX_LOCAL_AI_LANE_WAIT_SECONDS=60' not in env: fail('.env.example local AI lane wait not updated')
print('ScoutBox 0.10.75 targeted regressions passed.')
