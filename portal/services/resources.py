"""Runtime resource telemetry helpers.

ScoutBox prefers a small host-side telemetry bridge when running in Docker so
macOS/Linux host RAM, disk and GPU counters are not confused with container
limits. All probes are best-effort and deliberately fail closed to
"unavailable" rather than raising into a dashboard/resource page.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

BRIDGE_MAX_AGE_SECONDS=35
GPU_CARRY_FORWARD_SECONDS=15*60
BRIDGE_PATHS=(
    os.environ.get('SCOUTBOX_HOST_TELEMETRY_FILE',''),
    '/app/.scoutbox-runtime/host_telemetry.json',
    '.scoutbox-runtime/host_telemetry.json',
)
HOST_IDENTITY_PATHS=(
    '/app/.scoutbox-runtime/host_identity.json',
    '.scoutbox-runtime/host_identity.json',
)

def _bridge_snapshot_raw():
    """Return the newest readable host bridge snapshot even when it is stale.

    Callers that need utilization must still enforce ``BRIDGE_MAX_AGE_SECONDS``.
    Keeping the raw age available is important for telemetry health diagnostics: an
    absent bridge and a bridge that stopped updating are different failure modes.
    """
    newest={}
    newest_captured=0.0
    for raw in BRIDGE_PATHS:
        if not raw:
            continue
        try:
            data=json.loads(Path(raw).read_text())
            captured=float(data.get('captured_at') or 0)
            if captured>newest_captured:
                newest=data; newest_captured=captured
        except Exception:
            continue
    return newest


def _bridge_snapshot():
    data=_bridge_snapshot_raw()
    if not data:
        return {}
    try:
        captured=float(data.get('captured_at') or 0)
        if not captured or time.time()-captured>BRIDGE_MAX_AGE_SECONDS:
            return {}
    except Exception:
        return {}
    return data


def bridge_telemetry_status():
    """Return host-bridge/GPU freshness metadata without fabricating utilization."""
    raw=_bridge_snapshot_raw()
    now=time.time()
    captured=float(raw.get('captured_at') or 0) if raw else 0.0
    bridge_age=max(0.0,now-captured) if captured else None
    gpu_age=raw.get('gpu_sample_age_seconds') if raw else None
    try:
        gpu_age=None if gpu_age is None else max(0.0,float(gpu_age))
    except Exception:
        gpu_age=None
    state=str((raw or {}).get('gpu_telemetry_state') or '').strip().lower()
    if not state:
        state='fresh' if raw and raw.get('gpu_percent') is not None else ('bridge_stale' if raw else 'bridge_missing')
    if bridge_age is not None and bridge_age>BRIDGE_MAX_AGE_SECONDS:
        state='bridge_stale'
    return {
        'bridge_present':bool(raw),
        'bridge_age_seconds':None if bridge_age is None else round(bridge_age,1),
        'bridge_fresh':bool(captured and bridge_age is not None and bridge_age<=BRIDGE_MAX_AGE_SECONDS),
        'gpu_sample_age_seconds':gpu_age,
        'gpu_telemetry_state':state,
        'gpu_sample_at':(raw or {}).get('gpu_sample_at'),
    }

def _host_identity_snapshot():
    for raw in HOST_IDENTITY_PATHS:
        try:
            data=json.loads(Path(raw).read_text())
            if data.get('system') or data.get('platform'):
                return data
        except Exception:
            continue
    return {}

def _macos_gpu_telemetry():
    if platform.system().lower() != 'darwin':
        return None, None, ''
    label=''
    if shutil.which('system_profiler'):
        try:
            raw=subprocess.check_output(['system_profiler','SPDisplaysDataType'],text=True,timeout=3,stderr=subprocess.DEVNULL)
            match=re.search(r'Chipset Model:\s*(.+)',raw)
            if match: label=match.group(1).strip()[:200]
        except Exception: pass
    if not label and platform.machine().lower() in ('arm64','aarch64'):
        label='Apple Silicon GPU'
    if shutil.which('ioreg'):
        for cls in ('AGXAccelerator','IOAccelerator'):
            try:
                raw=subprocess.check_output(['ioreg','-r','-d','1','-w','0','-c',cls],text=True,timeout=3,stderr=subprocess.DEVNULL)
                probes=(r'"Device Utilization %"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Activity\(%\)"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Core Utilization"\s*=\s*(\d+(?:\.\d+)?)')
                for pattern in probes:
                    m=re.search(pattern,raw,re.I)
                    if m: return max(0.0,min(100.0,float(m.group(1)))), None, label or 'macOS GPU'
            except Exception: pass
    if shutil.which('powermetrics'):
        commands=[['powermetrics','--samplers','gpu_power','-n','1','-i','100']]
        if shutil.which('sudo'): commands.append(['sudo','-n','powermetrics','--samplers','gpu_power','-n','1','-i','100'])
        for cmd in commands:
            try:
                raw=subprocess.check_output(cmd,text=True,timeout=4,stderr=subprocess.DEVNULL)
                for pattern in (r'GPU active residency:\s*(\d+(?:\.\d+)?)%',r'GPU active:\s*(\d+(?:\.\d+)?)%'):
                    m=re.search(pattern,raw,re.I)
                    if m: return max(0.0,min(100.0,float(m.group(1)))), None, label or 'macOS GPU'
            except Exception: pass
    return None, None, label

def host_resource_totals(path='/'):
    """Best-effort host memory/disk totals and identity; never raises."""
    out={'memory_used_mb':0,'memory_total_mb':0,'memory_percent':0.0,'disk_used_mb':0,'disk_total_mb':0,'disk_free_mb':0,
         'cpu_percent':None,'cpu_count':os.cpu_count() or 0,'hostname':platform.node() or 'runtime','platform':f'{platform.system()} {platform.machine()}'.strip(),
         'os_label':f'{platform.system()} {platform.release()}'.strip(),'storage_label':'disk'}
    bridge=_bridge_snapshot()
    if bridge:
        for key in tuple(out)+('gpu_percent','gpu_memory_percent','gpu_label','gpu_vram_used_mb','gpu_vram_total_mb'):
            if key in bridge and bridge[key] is not None: out[key]=bridge[key]
        return out
    # Static host identity survives even when Python host telemetry is unavailable.
    # It is intentionally used only for OS/architecture identity, never fabricated
    # utilization or memory counters.
    ident=_host_identity_snapshot()
    if ident:
        system=str(ident.get('system') or '').strip(); machine=str(ident.get('machine') or '').strip()
        out['platform']=str(ident.get('platform') or f'{system} {machine}').strip()
        if system.lower()=='darwin': out['os_label']='macOS'
        elif system: out['os_label']=system
    try:
        import psutil
        vm=psutil.virtual_memory(); out.update(memory_used_mb=int(vm.used/(1024**2)),memory_total_mb=int(vm.total/(1024**2)),memory_percent=float(vm.percent),cpu_percent=float(psutil.cpu_percent(interval=0.05)))
        du=psutil.disk_usage(path); out.update(disk_used_mb=int(du.used/(1024**2)),disk_total_mb=int(du.total/(1024**2)),disk_free_mb=int(du.free/(1024**2)))
    except Exception: pass
    try:
        system=platform.system().lower()
        if system=='darwin':
            ver=platform.mac_ver()[0] or platform.release(); out['os_label']=f'macOS {ver}'.strip()
            if shutil.which('diskutil'):
                raw=subprocess.check_output(['diskutil','info','/'],text=True,timeout=3,stderr=subprocess.DEVNULL)
                out['storage_label']='SSD' if re.search(r'(?im)^\s*Solid State:\s*Yes',raw) else 'disk'
        elif system=='linux':
            pretty=''
            try:
                for line in Path('/etc/os-release').read_text().splitlines():
                    if line.startswith('PRETTY_NAME='): pretty=line.split('=',1)[1].strip().strip('\"'); break
            except Exception: pass
            out['os_label']=pretty or f'Linux {platform.release()}'
            if shutil.which('lsblk'):
                raw=subprocess.check_output(['lsblk','-dno','ROTA,TYPE'],text=True,timeout=3,stderr=subprocess.DEVNULL)
                vals=[ln.split()[0] for ln in raw.splitlines() if ln.split() and len(ln.split())>1 and ln.split()[1]=='disk']
                if vals and all(v=='0' for v in vals): out['storage_label']='SSD'
    except Exception: pass
    return out

def gpu_telemetry_detail():
    """Return GPU utilization, memory utilization, label and discrete VRAM MB.

    On Apple unified-memory systems VRAM values deliberately remain ``None``.
    """
    bridge=_bridge_snapshot()
    if bridge and (bridge.get('gpu_percent') is not None or bridge.get('gpu_label')):
        return (bridge.get('gpu_percent'),bridge.get('gpu_memory_percent'),str(bridge.get('gpu_label') or ''),
                bridge.get('gpu_vram_used_mb'),bridge.get('gpu_vram_total_mb'))
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        try:
            count=int(pynvml.nvmlDeviceGetCount() or 0)
            if count:
                utils=[]; mems=[]; names=[]; useds=[]; totals=[]
                for idx in range(count):
                    handle=pynvml.nvmlDeviceGetHandleByIndex(idx); util=pynvml.nvmlDeviceGetUtilizationRates(handle); memory=pynvml.nvmlDeviceGetMemoryInfo(handle); name=pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name,bytes): name=name.decode('utf-8','replace')
                    utils.append(float(getattr(util,'gpu',0.0))); total=float(getattr(memory,'total',0.0) or 0.0); used=float(getattr(memory,'used',0.0) or 0.0); mems.append((used*100.0/total) if total else 0.0); names.append(str(name or f'GPU {idx}')); useds.append(used/(1024**2)); totals.append(total/(1024**2))
                return max(utils),max(mems),' + '.join(names[:3]),sum(useds),sum(totals)
        finally:
            try:pynvml.nvmlShutdown()
            except Exception:pass
    except Exception: pass
    mac=_macos_gpu_telemetry()
    if mac[0] is not None or mac[2]: return mac[0],mac[1],mac[2],None,None
    # In Docker on macOS, the process itself reports Linux. Keep the host GPU identity
    # useful even if the telemetry bridge is stale/unavailable; utilization remains unknown.
    ident=_host_identity_snapshot()
    if str(ident.get('system') or '').lower()=='darwin':
        machine=str(ident.get('machine') or '').lower()
        return None,None,('Apple Silicon GPU' if machine in ('arm64','aarch64') else 'macOS GPU'),None,None
    if shutil.which('nvidia-smi'):
        try:
            raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total','--format=csv,noheader,nounits'],text=True,timeout=3,stderr=subprocess.DEVNULL)
            rows=[]
            for line in raw.splitlines():
                parts=[x.strip() for x in line.split(',')]
                if len(parts)>=5: rows.append((parts[0],float(parts[1]),float(parts[2]),float(parts[3]),float(parts[4])))
            if rows:return max(x[1] for x in rows),max(x[2] for x in rows),' + '.join(x[0] for x in rows[:3]),sum(x[3] for x in rows),sum(x[4] for x in rows)
        except Exception: pass
    # Linux AMD/DRM fallback.
    try:
        vals=[]
        for p in Path('/sys/class/drm').glob('card*/device/gpu_busy_percent'):
            try:vals.append(float(p.read_text().strip()))
            except Exception:pass
        if vals:return max(vals),None,'Linux DRM GPU',None,None
    except Exception:pass
    return None,None,'',None,None

def gpu_telemetry():
    """Return (gpu_percent, gpu_memory_percent, label), best effort."""
    gpu,mem,label,_,_=gpu_telemetry_detail()
    return gpu,mem,label

def host_cpu_percent():
    """Best-effort host CPU percentage using bridge first; never raises."""
    snap=_bridge_snapshot()
    try:
        if snap.get('cpu_percent') is not None:
            return float(snap.get('cpu_percent') or 0.0)
    except Exception:
        pass
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.05))
    except Exception:
        return 0.0

def gpu_telemetry_detail_with_status():
    """GPU detail plus freshness metadata used when persisting ResourceSample."""
    gpu,mem,label,vram_used,vram_total=gpu_telemetry_detail()
    status=bridge_telemetry_status()
    state=status.get('gpu_telemetry_state') or ('fresh' if gpu is not None else 'unavailable')
    # Native Linux/NVIDIA probes do not use the host bridge; a successful direct probe
    # is fresh even if the bridge is absent.
    if gpu is not None and state in {'bridge_missing','bridge_stale','unavailable'}:
        state='fresh'
        status['gpu_sample_age_seconds']=0.0
    status['gpu_telemetry_state']=state
    return gpu,mem,label,vram_used,vram_total,status


def _merge_hourly_sample(sample):
    """Increment the durable hourly archive from one persisted ResourceSample."""
    from django.db import transaction
    from django.utils import timezone
    from portal.models import ResourceHourly

    at=sample.at or timezone.now()
    local=timezone.localtime(at) if timezone.is_aware(at) else at
    hour_local=local.replace(minute=0,second=0,microsecond=0)
    hour=hour_local.astimezone(at.tzinfo) if timezone.is_aware(at) else hour_local
    with transaction.atomic():
        row,created=ResourceHourly.objects.select_for_update().get_or_create(hour=hour)
        old_count=int(row.sample_count or 0)
        new_count=old_count+1
        cpu=float(sample.cpu_percent or 0.0); mem=float(sample.memory_percent or 0.0)
        row.cpu_avg=cpu if not old_count or row.cpu_avg is None else ((float(row.cpu_avg)*old_count)+cpu)/new_count
        row.memory_avg=mem if not old_count or row.memory_avg is None else ((float(row.memory_avg)*old_count)+mem)/new_count
        row.cpu_min=cpu if row.cpu_min is None else min(float(row.cpu_min),cpu)
        row.cpu_max=cpu if row.cpu_max is None else max(float(row.cpu_max),cpu)
        row.memory_min=mem if row.memory_min is None else min(float(row.memory_min),mem)
        row.memory_max=mem if row.memory_max is None else max(float(row.memory_max),mem)
        row.sample_count=new_count
        gpu=sample.gpu_percent
        if gpu is not None:
            gpu=float(gpu); old_gpu_count=int(row.gpu_sample_count or 0); new_gpu_count=old_gpu_count+1
            row.gpu_avg=gpu if not old_gpu_count or row.gpu_avg is None else ((float(row.gpu_avg)*old_gpu_count)+gpu)/new_gpu_count
            row.gpu_min=gpu if row.gpu_min is None else min(float(row.gpu_min),gpu)
            row.gpu_max=gpu if row.gpu_max is None else max(float(row.gpu_max),gpu)
            row.gpu_sample_count=new_gpu_count
            if str(getattr(sample,'gpu_telemetry_state','') or '').startswith('stale'):
                row.gpu_stale_count=int(row.gpu_stale_count or 0)+1
        row.memory_used_mb=int(sample.memory_used_mb or 0); row.memory_total_mb=int(sample.memory_total_mb or 0)
        row.disk_used_mb=int(sample.disk_used_mb or 0); row.disk_total_mb=int(sample.disk_total_mb or 0)
        row.gpu_label=str(sample.gpu_label or row.gpu_label or '')[:200]
        row.gpu_vram_used_mb=sample.gpu_vram_used_mb; row.gpu_vram_total_mb=sample.gpu_vram_total_mb
        row.last_sample_at=at
        row.save()
    return row


def capture_resource_sample(*, carry_seconds=GPU_CARRY_FORWARD_SECONDS):
    """Persist one coherent host-resource sample and its durable hourly roll-up.

    GPU probes are intentionally more fragile than CPU/RAM probes on macOS. A brief
    probe interruption therefore carries the last measured GPU utilization forward for
    a bounded interval and marks it ``stale_carry`` instead of storing NULL. This keeps
    chart history continuous without pretending a stale value is a fresh measurement.
    """
    from django.utils import timezone
    from portal.models import ResourceSample

    now=timezone.now()
    cpu=float(host_cpu_percent()); totals=host_resource_totals()
    gpu,gpu_mem,label,vram_used,vram_total,status=gpu_telemetry_detail_with_status()
    state=str(status.get('gpu_telemetry_state') or ('fresh' if gpu is not None else 'unavailable'))
    gpu_age=status.get('gpu_sample_age_seconds')
    if gpu is None:
        previous=(ResourceSample.objects.exclude(gpu_percent__isnull=True).order_by('-at').first())
        if previous is not None:
            elapsed=max(0.0,(now-previous.at).total_seconds())
            previous_age=float(getattr(previous,'gpu_sample_age_seconds',0.0) or 0.0)
            effective_age=elapsed+previous_age
            if effective_age<=max(0.0,float(carry_seconds or 0)):
                gpu=previous.gpu_percent; gpu_mem=previous.gpu_memory_percent
                vram_used=previous.gpu_vram_used_mb; vram_total=previous.gpu_vram_total_mb
                label=label or previous.gpu_label
                gpu_age=effective_age; state='stale_carry'
    if gpu is not None and state in {'','unavailable','bridge_missing','bridge_stale'}:
        state='fresh'
    bridge_age=status.get('bridge_age_seconds')
    sample=ResourceSample.objects.create(
        cpu_percent=cpu,
        memory_percent=float(totals['memory_percent']),
        memory_used_mb=totals['memory_used_mb'],memory_total_mb=totals['memory_total_mb'],
        disk_used_mb=totals['disk_used_mb'],disk_total_mb=totals['disk_total_mb'],
        gpu_percent=gpu,gpu_memory_percent=gpu_mem,
        gpu_vram_used_mb=None if vram_used is None else max(0,int(vram_used)),
        gpu_vram_total_mb=None if vram_total is None else max(0,int(vram_total)),
        gpu_label=label or '',
        gpu_sample_age_seconds=None if gpu_age is None else max(0.0,float(gpu_age)),
        gpu_telemetry_state=state[:24],
        host_telemetry_age_seconds=None if bridge_age is None else max(0.0,float(bridge_age)),
    )
    try:
        _merge_hourly_sample(sample)
    except Exception:
        # Raw telemetry must continue even if a roll-up row is temporarily locked or
        # unavailable. The next sample will resume the archive automatically.
        pass
    return sample

