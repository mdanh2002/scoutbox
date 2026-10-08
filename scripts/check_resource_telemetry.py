#!/usr/bin/env python3
"""Small runtime health probe used by smoke tests and support diagnostics."""
from __future__ import annotations
import argparse
import os
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE','opportunity_portal.settings')
import django  # noqa: E402
django.setup()

from django.utils import timezone  # noqa: E402
from portal.models import ResourceSample, ResourceHourly  # noqa: E402


def latest_status():
    row=ResourceSample.objects.order_by('-at').first()
    if row is None:
        return None,None
    return row,max(0.0,(timezone.now()-row.at).total_seconds())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--wait-seconds',type=float,default=30.0)
    ap.add_argument('--max-sample-age',type=float,default=60.0)
    ap.add_argument('--gpu',action='store_true')
    args=ap.parse_args()
    deadline=time.monotonic()+max(0.0,args.wait_seconds)
    row=age=None
    while True:
        row,age=latest_status()
        if row is not None and age is not None and age<=args.max_sample_age:
            break
        if time.monotonic()>=deadline:
            print(f'ResourceSample stale or missing (age={age!r}s)',file=sys.stderr)
            return 1
        time.sleep(2.0)
    if not ResourceHourly.objects.filter(hour__lte=row.at).exists():
        print('ResourceSample is fresh but durable ResourceHourly archive is not advancing.',file=sys.stderr)
        return 1
    if args.gpu:
        state=str(getattr(row,'gpu_telemetry_state','') or 'unknown')
        label=str(getattr(row,'gpu_label','') or '')
        if label and row.gpu_percent is None:
            print(f'GPU telemetry unavailable for {label} (state={state}).',file=sys.stderr)
            return 2
        print(f'GPU telemetry state={state}; age={getattr(row,"gpu_sample_age_seconds",None)!r}s; label={label or "none"}')
    else:
        print(f'ResourceSample age={age:.1f}s; archive advancing; gpu_state={getattr(row,"gpu_telemetry_state","") or "unknown"}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
