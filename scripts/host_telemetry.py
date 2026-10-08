#!/usr/bin/env python3
"""Best-effort host telemetry bridge for ScoutBox Docker deployments.

Runs on the host and atomically writes a small JSON snapshot consumed by the
ScoutBox containers. Slow GPU probes run independently from the heartbeat so a
busy/unavailable GPU command cannot make otherwise healthy host telemetry stale.
Every probe is optional; missing commands/counters never make the process fail.
"""
from __future__ import annotations
import argparse, json, os, platform, re, shutil, socket, subprocess, threading, time
from pathlib import Path

MB=1024*1024
_HOST_IDENTITY_CACHE=None
_MAC_GPU_LABEL=None


def run(cmd, timeout=3):
    try:
        return subprocess.check_output(cmd, text=True, timeout=timeout, stderr=subprocess.DEVNULL)
    except Exception:
        return ''


def clamp(v):
    try: return max(0.0,min(100.0,float(v)))
    except Exception: return None


def disk():
    try:
        s=os.statvfs('/')
        total=s.f_blocks*s.f_frsize; free=s.f_bavail*s.f_frsize; used=max(0,total-free)
        return int(used/MB),int(total/MB),int(free/MB)
    except Exception: return 0,0,0


def mac_cpu():
    raw=run(['top','-l','1','-n','0'],4)
    m=re.search(r'CPU usage:\s*[\d.]+% user,\s*[\d.]+% sys,\s*([\d.]+)% idle',raw,re.I)
    return clamp(100-float(m.group(1))) if m else None


def linux_cpu():
    def readstat():
        try:
            vals=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
            return sum(vals), vals[3]+(vals[4] if len(vals)>4 else 0)
        except Exception:return None
    a=readstat(); time.sleep(.12); b=readstat()
    if not a or not b:return None
    total=b[0]-a[0]; idle=b[1]-a[1]
    return clamp(100*(1-idle/max(1,total)))


def mac_memory():
    try: total=int(run(['sysctl','-n','hw.memsize']).strip())
    except Exception: total=0
    raw=run(['vm_stat'])
    page_m=re.search(r'page size of (\d+) bytes',raw,re.I); page=int(page_m.group(1)) if page_m else 4096
    vals={}
    for k,v in re.findall(r'^([^:]+):\s*([\d.]+)\.?$',raw,re.M):
        try:vals[k.strip().lower()]=float(v)
        except Exception:pass
    available=sum(vals.get(k,0) for k in ('pages free','pages inactive','pages speculative','pages purgeable'))*page
    used=max(0,total-int(available)) if total else 0
    pct=(used*100/total) if total else 0
    return int(used/MB),int(total/MB),pct


def linux_memory():
    try:
        vals={}
        for line in Path('/proc/meminfo').read_text().splitlines():
            k,v=line.split(':',1); vals[k]=int(v.strip().split()[0])*1024
        total=vals.get('MemTotal',0); avail=vals.get('MemAvailable',vals.get('MemFree',0)); used=max(0,total-avail)
        return int(used/MB),int(total/MB),(used*100/total if total else 0)
    except Exception:return 0,0,0


def mac_gpu_label():
    global _MAC_GPU_LABEL
    if _MAC_GPU_LABEL is not None:
        return _MAC_GPU_LABEL
    label=''
    raw=run(['system_profiler','SPDisplaysDataType'],4) if shutil.which('system_profiler') else ''
    m=re.search(r'(?:Chipset Model|Chip):\s*(.+)',raw)
    if m: label=m.group(1).strip()[:200]
    if not label and platform.machine().lower() in ('arm64','aarch64'):
        label='Apple Silicon GPU'
    _MAC_GPU_LABEL=label
    return label


def mac_gpu():
    label=mac_gpu_label()
    if shutil.which('ioreg'):
        for cls in ('AGXAccelerator','IOAccelerator'):
            raw=run(['ioreg','-r','-d','1','-w','0','-c',cls],3)
            for pattern in (r'"Device Utilization %"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Activity\(%\)"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Core Utilization"\s*=\s*(\d+(?:\.\d+)?)'):
                m=re.search(pattern,raw,re.I)
                if m:return clamp(m.group(1)),None,label or 'macOS GPU',None,None
    # Some Apple Silicon releases expose PerformanceStatistics only on a broader ioreg dump.
    if shutil.which('ioreg'):
        raw=run(['ioreg','-l','-w','0'],4)
        for pattern in (r'"Device Utilization %"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Activity\(%\)"\s*=\s*(\d+(?:\.\d+)?)',r'"GPU Core Utilization"\s*=\s*(\d+(?:\.\d+)?)'):
            m=re.search(pattern,raw,re.I)
            if m:return clamp(m.group(1)),None,label or 'macOS GPU',None,None
    # powermetrics normally needs privilege on macOS. Try directly first, then
    # passwordless sudo (-n) so ScoutBox never opens a prompt or blocks startup.
    if shutil.which('powermetrics'):
        commands=[['powermetrics','--samplers','gpu_power','-n','1','-i','100']]
        if shutil.which('sudo'): commands.append(['sudo','-n','powermetrics','--samplers','gpu_power','-n','1','-i','100'])
        for cmd in commands:
            raw=run(cmd,4)
            for pattern in (r'GPU active residency:\s*(\d+(?:\.\d+)?)%', r'GPU active:\s*(\d+(?:\.\d+)?)%'):
                m=re.search(pattern,raw,re.I)
                if m:return clamp(m.group(1)),None,label or 'macOS GPU',None,None
    return None,None,label,None,None


def linux_gpu():
    if shutil.which('nvidia-smi'):
        raw=run(['nvidia-smi','--query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total','--format=csv,noheader,nounits'],3)
        rows=[]
        for line in raw.splitlines():
            p=[x.strip() for x in line.split(',')]
            if len(p)>=5:
                try:rows.append((p[0],float(p[1]),float(p[2]),float(p[3]),float(p[4])))
                except Exception:pass
        if rows:return max(x[1] for x in rows),max(x[2] for x in rows),' + '.join(x[0] for x in rows[:3]),sum(x[3] for x in rows),sum(x[4] for x in rows)
    vals=[]
    for p in Path('/sys/class/drm').glob('card*/device/gpu_busy_percent'):
        try:vals.append(float(p.read_text().strip()))
        except Exception:pass
    if vals:return max(vals),None,'Linux DRM GPU',None,None
    return None,None,'',None,None


class GpuSampler:
    """Probe GPU independently while preserving bounded measurement continuity.

    macOS GPU probes can fail briefly during sleep/wake, high load or command races.
    Older ScoutBox releases converted that transient failure to NULL after 30 seconds,
    permanently punching holes into ResourceSample history. 0.11.144 keeps the last
    successful measurement for a bounded stale window and emits explicit quality state
    so callers never mistake a carried value for a fresh probe.
    """
    def __init__(self, interval=5.0, max_age=900.0, initial_state=None):
        self.interval=max(2.0,float(interval)); self.max_age=max(30.0,float(max_age))
        self.lock=threading.Lock(); self.stop_event=threading.Event()
        default_label='Apple Silicon GPU' if platform.system().lower()=='darwin' and platform.machine().lower() in ('arm64','aarch64') else ''
        self.state={'gpu_percent':None,'gpu_memory_percent':None,'gpu_label':default_label,'gpu_vram_used_mb':None,'gpu_vram_total_mb':None,'gpu_sample_at':0.0,'gpu_probe_failures':0}
        if isinstance(initial_state,dict):
            try:
                sample_at=float(initial_state.get('gpu_sample_at') or 0)
                if sample_at and time.time()-sample_at<=self.max_age and initial_state.get('gpu_percent') is not None:
                    self.state.update(
                        gpu_percent=initial_state.get('gpu_percent'),
                        gpu_memory_percent=initial_state.get('gpu_memory_percent'),
                        gpu_label=initial_state.get('gpu_label') or default_label,
                        gpu_vram_used_mb=initial_state.get('gpu_vram_used_mb'),
                        gpu_vram_total_mb=initial_state.get('gpu_vram_total_mb'),
                        gpu_sample_at=sample_at,
                    )
            except Exception:
                pass
        self.thread=threading.Thread(target=self._loop,name='scoutbox-gpu-telemetry',daemon=True)

    def start(self):
        self.thread.start(); return self

    def stop(self):
        self.stop_event.set()

    def _probe(self):
        system=platform.system().lower()
        if system=='darwin': return mac_gpu()
        if system=='linux': return linux_gpu()
        return None,None,'',None,None

    def _loop(self):
        while not self.stop_event.is_set():
            started=time.monotonic()
            try:
                gpu,gmem,label,vram_used,vram_total=self._probe()
                now=time.time()
                with self.lock:
                    if label: self.state['gpu_label']=label
                    if gpu is not None:
                        self.state.update(gpu_percent=gpu,gpu_memory_percent=gmem,gpu_vram_used_mb=vram_used,gpu_vram_total_mb=vram_total,gpu_sample_at=now,gpu_probe_failures=0)
                    else:
                        self.state['gpu_probe_failures']=int(self.state.get('gpu_probe_failures') or 0)+1
            except Exception:
                with self.lock:
                    self.state['gpu_probe_failures']=int(self.state.get('gpu_probe_failures') or 0)+1
            elapsed=time.monotonic()-started
            self.stop_event.wait(max(0.25,self.interval-elapsed))

    def read(self):
        with self.lock: out=dict(self.state)
        sample_at=float(out.get('gpu_sample_at') or 0)
        age=max(0.0,time.time()-sample_at) if sample_at else None
        if not sample_at:
            state='unavailable'
        elif age<=max(self.interval*2.5,15.0):
            state='fresh'
        elif age<=self.max_age:
            state='stale'
        else:
            state='unavailable'
            out.update(gpu_percent=None,gpu_memory_percent=None,gpu_vram_used_mb=None,gpu_vram_total_mb=None)
        out['gpu_sample_age_seconds']=round(age,1) if age is not None else None
        out['gpu_telemetry_state']=state
        return out


def host_identity():
    global _HOST_IDENTITY_CACHE
    if _HOST_IDENTITY_CACHE is not None:
        return _HOST_IDENTITY_CACHE
    system=platform.system().lower(); os_label=f'{platform.system()} {platform.release()}'.strip(); storage='disk'
    try:
        if system=='darwin':
            os_label=f'macOS {platform.mac_ver()[0] or platform.release()}'
            raw=run(['diskutil','info','/'],3) if shutil.which('diskutil') else ''
            if re.search(r'(?im)^\s*Solid State:\s*Yes',raw): storage='SSD'
        elif system=='linux':
            try:
                for line in Path('/etc/os-release').read_text().splitlines():
                    if line.startswith('PRETTY_NAME='):
                        os_label=line.split('=',1)[1].strip().strip('"'); break
            except Exception: pass
            raw=run(['lsblk','-dno','ROTA,TYPE'],3) if shutil.which('lsblk') else ''
            vals=[ln.split()[0] for ln in raw.splitlines() if len(ln.split())>1 and ln.split()[1]=='disk']
            if vals and all(v=='0' for v in vals): storage='SSD'
    except Exception: pass
    _HOST_IDENTITY_CACHE=(os_label,storage)
    return _HOST_IDENTITY_CACHE


def snapshot(gpu_state=None):
    system=platform.system().lower()
    if system=='darwin':
        cpu=mac_cpu(); mu,mt,mp=mac_memory()
    elif system=='linux':
        cpu=linux_cpu(); mu,mt,mp=linux_memory()
    else:
        cpu=None; mu=mt=0; mp=0
    if gpu_state is None:
        if system=='darwin': gpu,gmem,glabel,vram_used,vram_total=mac_gpu()
        elif system=='linux': gpu,gmem,glabel,vram_used,vram_total=linux_gpu()
        else: gpu=gmem=None; glabel=''; vram_used=vram_total=None
        gpu_state={'gpu_percent':gpu,'gpu_memory_percent':gmem,'gpu_label':glabel,'gpu_vram_used_mb':vram_used,'gpu_vram_total_mb':vram_total}
    du,dt,df=disk(); os_label,storage_label=host_identity()
    data={
        'captured_at':time.time(),'hostname':socket.gethostname(),'platform':f'{platform.system()} {platform.machine()}'.strip(),
        'cpu_count':os.cpu_count() or 0,'cpu_percent':cpu,'memory_used_mb':mu,'memory_total_mb':mt,'memory_percent':mp,
        'disk_used_mb':du,'disk_total_mb':dt,'disk_free_mb':df,'os_label':os_label,'storage_label':storage_label,
        'gpu_percent':gpu_state.get('gpu_percent'),'gpu_memory_percent':gpu_state.get('gpu_memory_percent'),'gpu_label':gpu_state.get('gpu_label') or '',
        'gpu_vram_used_mb':gpu_state.get('gpu_vram_used_mb'),'gpu_vram_total_mb':gpu_state.get('gpu_vram_total_mb'),
    }
    if 'gpu_sample_age_seconds' in gpu_state: data['gpu_sample_age_seconds']=gpu_state.get('gpu_sample_age_seconds')
    if 'gpu_sample_at' in gpu_state: data['gpu_sample_at']=gpu_state.get('gpu_sample_at')
    if 'gpu_telemetry_state' in gpu_state: data['gpu_telemetry_state']=gpu_state.get('gpu_telemetry_state')
    if 'gpu_probe_failures' in gpu_state: data['gpu_probe_failures']=gpu_state.get('gpu_probe_failures')
    return data


def write_atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,separators=(',',':'))); os.replace(tmp,path)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='.scoutbox-runtime/host_telemetry.json'); ap.add_argument('--interval',type=float,default=5.0); ap.add_argument('--gpu-interval',type=float,default=5.0); ap.add_argument('--once',action='store_true'); args=ap.parse_args()
    out=Path(args.output).expanduser().resolve()
    if args.once:
        try: write_atomic(out,snapshot())
        except Exception: pass
        return
    previous={}
    try:
        previous=json.loads(out.read_text()) if out.is_file() else {}
    except Exception:
        previous={}
    # Fifteen minutes is long enough to bridge transient macOS probe failures but
    # short enough that an unavailable GPU cannot masquerade as live indefinitely.
    gpu_sampler=GpuSampler(interval=args.gpu_interval,max_age=max(900.0,args.gpu_interval*12),initial_state=previous).start()
    try:
        while True:
            started=time.monotonic()
            try:write_atomic(out,snapshot(gpu_sampler.read()))
            except Exception:pass
            elapsed=time.monotonic()-started
            time.sleep(max(0.25,max(2.0,args.interval)-elapsed))
    finally:
        gpu_sampler.stop()


if __name__=='__main__':main()
