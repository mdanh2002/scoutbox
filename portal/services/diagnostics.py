import shutil
import smtplib
import subprocess
import re
from django.conf import settings
from celery import current_app
from django.db import connection
from portal.models import BlogStatsConfig, SearchSource
from .mailbox import active_profile, connect as imap_connect
from .notifications import outgoing_method
from .ollama import diagnostics as ollama_diagnostics


def run_system_diagnostics():
    out=[]
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1'); cur.fetchone()
            cur.execute('SHOW server_version'); pg_version=str(cur.fetchone()[0] or '').strip()
        out.append(('PostgreSQL','OK',f'{pg_version} · Database reachable' if pg_version else 'Database reachable'))
    except Exception as exc:
        out.append(('PostgreSQL','ERROR',str(exc)[:300]))
    try:
        import redis
        client=redis.Redis.from_url(settings.CELERY_BROKER_URL,socket_connect_timeout=4,socket_timeout=4)
        client.ping()
        redis_version=str((client.info('server') or {}).get('redis_version') or '').strip()
        out.append(('Redis','OK',f'{redis_version} · Broker reachable' if redis_version else 'Broker reachable'))
    except Exception as exc:
        out.append(('Redis','ERROR',str(exc)[:300]))
    try:
        queues=current_app.control.inspect(timeout=1.2).active_queues() or {}
        seen=set()
        for rows in queues.values():
            for row in rows or []:
                name=str((row or {}).get('name') or '').strip()
                if name: seen.add(name)
        required={'celery','discovery'}
        missing=sorted(required-seen)
        if missing:
            out.append(('Celery workers','WARN',f"Missing queue consumer(s): {', '.join(missing)} · seen: {', '.join(sorted(seen)) or 'none'}"))
        else:
            out.append(('Celery workers','OK',f"Background + discovery queues active · {len(queues)} worker(s)"))
    except Exception as exc:
        out.append(('Celery workers','WARN',f'Worker inspection unavailable: {str(exc)[:220]}'))
    try:
        d=ollama_diagnostics(); version=str(d.get('version') or '').strip(); installed=len(d.get('installed') or []); detail=(f'{version} · {installed} installed' if version else f'{installed} installed'); out.append(('Ollama','OK' if d.get('ok') else 'WARN',detail[:300]))
    except Exception as exc:
        out.append(('Ollama','WARN',str(exc)[:300]))
    p=active_profile()
    if p:
        if p.imap_host and p.imap_username:
            try:
                im=imap_connect(p); im.logout(); out.append(('IMAP','OK',f'{p.get_template_display()}: {p.imap_host}:{p.imap_port}'))
            except Exception as exc: out.append(('IMAP','ERROR',str(exc)[:300]))
        else: out.append(('IMAP','WARN','Mailbox not configured'))
        if outgoing_method(p)=='resend':
            if p.resend_api_key_enc and p.notification_from_email:
                out.append(('Outgoing mail','OK','Resend API configured · api.resend.com'))
            else:
                out.append(('Outgoing mail','WARN','Resend API key or From email is missing'))
        elif p.smtp_host:
            try:
                smtp=smtplib.SMTP(p.smtp_host,p.smtp_port,timeout=5); smtp.ehlo()
                if p.smtp_tls: smtp.starttls(); smtp.ehlo()
                smtp.quit(); out.append(('Notification SMTP','OK',f'{p.smtp_host}:{p.smtp_port}'))
            except Exception as exc: out.append(('Notification SMTP','WARN',str(exc)[:300]))
        else: out.append(('Notification SMTP','WARN','Notification SMTP not configured'))
    else:
        out.extend([('IMAP','WARN','No active email profile'),('Outgoing mail','WARN','No active email profile')])
    lo=shutil.which('libreoffice') or shutil.which('soffice')
    if lo:
        lo_version=''
        try:
            proc=subprocess.run([lo,'--version'],capture_output=True,text=True,timeout=3,check=False)
            text=(proc.stdout or proc.stderr or '').strip().splitlines()[0] if (proc.stdout or proc.stderr) else ''
            match=re.search(r'LibreOffice\s+([^\s]+)',text,re.I)
            lo_version=match.group(1) if match else text.replace('LibreOffice','').strip()
        except Exception:
            lo_version=''
        detail=(f'LibreOffice {lo_version}' if lo_version else f'LibreOffice · {lo}')
        out.append(('Document conversion','OK',detail))
    else:
        out.append(('Document conversion','WARN','LibreOffice not found'))
    enabled=SearchSource.objects.filter(enabled=True,adapter_status='active').count()
    out.append(('Search adapters','OK' if enabled else 'WARN',f'{enabled} enabled adapter(s)'))
    try:
        cfg=BlogStatsConfig.objects.get_or_create(pk=1)[0]
        out.append(('External statistics','OK' if cfg.enabled else 'WARN','Enabled' if cfg.enabled else 'Disabled'))
    except Exception as exc:
        out.append(('External statistics','WARN',str(exc)[:300]))
    return out
