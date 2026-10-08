import time

from django.core.management.base import BaseCommand

from portal.tasks import resource_sample_tick


class Command(BaseCommand):
    help = 'Continuously persist ScoutBox resource telemetry without Celery/Beat scheduling.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=float, default=15.0)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        interval=max(2.0,float(options.get('interval') or 15.0))
        once=bool(options.get('once'))
        self.stdout.write(f'ScoutBox resource sampler started (interval={interval:g}s).')
        failures=0; gpu_degraded=0
        while True:
            started=time.monotonic()
            result=resource_sample_tick.run()
            if isinstance(result,dict) and result.get('error'):
                failures+=1
                # Avoid flooding Docker logs for a persistent database/system error.
                if failures==1 or failures%20==0:
                    self.stderr.write(f"Resource sample failed ({failures} consecutive): {result['error']}")
            else:
                failures=0
                state=str((result or {}).get('gpu_state') or '') if isinstance(result,dict) else ''
                if state in {'unavailable','bridge_missing','bridge_stale'}:
                    gpu_degraded+=1
                    # The sampler is alive, but GPU history is at risk. Make that visible in
                    # container logs instead of silently writing NULL for hours.
                    if gpu_degraded==1 or gpu_degraded%20==0:
                        self.stderr.write(f"GPU telemetry degraded ({gpu_degraded} consecutive samples; state={state or 'unknown'}).")
                else:
                    if gpu_degraded>=4:
                        self.stdout.write(f'GPU telemetry recovered after {gpu_degraded} degraded samples.')
                    gpu_degraded=0
            if once:
                return
            elapsed=time.monotonic()-started
            time.sleep(max(0.25,interval-elapsed))
