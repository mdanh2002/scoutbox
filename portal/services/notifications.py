import smtplib
from email.message import EmailMessage

import requests
from django.utils import timezone

from portal.models import MailEvent
from .crypto import decrypt
from .mailbox import active_profile

RESEND_ENDPOINT='https://api.resend.com/emails'


def outgoing_method(profile):
    """Internal development mail remains SMTP-only; External Mail may use Resend."""
    if profile and getattr(profile,'template','')=='external' and getattr(profile,'outgoing_method','smtp')=='resend':
        return 'resend'
    return 'smtp'


def outgoing_server_label(profile):
    if outgoing_method(profile)=='resend':
        return 'Resend API api.resend.com'
    if profile and profile.smtp_host:
        return f'SMTP {profile.smtp_host}:{profile.smtp_port}'
    return 'SMTP not configured'


def _sender_value(profile):
    email=(profile.notification_from_email or '').strip()
    name=(profile.notification_from_name or '').strip()
    return f'{name} <{email}>' if name else email


def _send_via_resend(profile, recipient, subject, body, html_body):
    key=decrypt(profile.resend_api_key_enc)
    if not key:
        raise RuntimeError('Resend API key is not configured')
    payload={
        'from':_sender_value(profile),
        'to':[recipient],
        'subject':subject,
        'text':body or '',
    }
    if html_body:
        payload['html']=html_body
    response=requests.post(
        RESEND_ENDPOINT,
        headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'ScoutBox/0.10.103'},
        json=payload,
        timeout=20,
    )
    try:
        data=response.json()
    except Exception:
        data={}
    if response.status_code < 200 or response.status_code >= 300:
        detail=''
        if isinstance(data,dict):
            detail=str(data.get('message') or data.get('error') or '').strip()
        if not detail:
            detail=(response.text or '').strip()[:500]
        raise RuntimeError(f'Resend API returned HTTP {response.status_code}'+(f': {detail}' if detail else ''))
    return str(data.get('id') or '') if isinstance(data,dict) else ''


def send_notification(recipient, subject, body, html_body=None, profile=None, metadata_extra=None):
    """Send portal-service mail only. Never use this function for an application email."""
    profile = profile or active_profile()
    if not profile:
        raise RuntimeError('No active email profile')
    method=outgoing_method(profile)
    if not profile.notification_from_email:
        raise RuntimeError('Outgoing From email is not configured')
    if method=='smtp' and not profile.smtp_host:
        raise RuntimeError('Notification SMTP is not configured')
    if method=='resend' and not profile.resend_api_key_enc:
        raise RuntimeError('Resend API is not configured')
    if not recipient:
        raise RuntimeError('Notification recipient is empty')

    msg = EmailMessage()
    msg['From'] = _sender_value(profile)
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content(body or '')
    if html_body:
        msg.add_alternative(html_body, subtype='html')

    metadata={'template':profile.template,'outgoing_method':method}
    if isinstance(metadata_extra,dict):
        metadata.update(metadata_extra)
    if method=='smtp':
        metadata.update({'smtp_host':profile.smtp_host,'smtp_port':profile.smtp_port})
    else:
        metadata.update({'provider':'resend','endpoint':'api.resend.com'})
    event = MailEvent.objects.create(
        kind='notification', subject=subject, sender=profile.notification_from_email,
        recipients=recipient, message_id=msg.get('Message-ID',''), body_excerpt=(body or '')[:1000],
        body_text=body or '', body_html=html_body or '', delivery_status='queued',
        server=outgoing_server_label(profile),
        occurred_at=timezone.now(), metadata=metadata,
    )

    if method=='resend':
        try:
            message_id=_send_via_resend(profile,recipient,subject,body,html_body)
            event.delivery_status='accepted'; event.delivery_error=''
            if message_id:
                event.message_id=message_id
            event.save(update_fields=['delivery_status','delivery_error','message_id'])
            return event
        except Exception as exc:
            event.delivery_status='failed'; event.delivery_error=str(exc)[:1000]
            event.save(update_fields=['delivery_status','delivery_error'])
            raise

    smtp=None
    try:
        smtp=smtplib.SMTP(profile.smtp_host, profile.smtp_port, timeout=15)
        smtp.ehlo()
        if profile.smtp_tls:
            smtp.starttls(); smtp.ehlo()
        if profile.smtp_username:
            smtp.login(profile.smtp_username, decrypt(profile.smtp_password_enc))
        refused=smtp.send_message(msg) or {}
        if refused:
            event.delivery_status='failed'; event.delivery_error=str(refused)[:1000]
            event.save(update_fields=['delivery_status','delivery_error'])
            raise RuntimeError(f'SMTP refused recipient(s): {refused}')
        event.delivery_status='accepted'; event.delivery_error=''; event.save(update_fields=['delivery_status','delivery_error'])
        return event
    except Exception as exc:
        event.delivery_status='failed'; event.delivery_error=str(exc)[:1000]; event.save(update_fields=['delivery_status','delivery_error'])
        raise
    finally:
        if smtp:
            try: smtp.quit()
            except Exception: pass


def refresh_resend_delivery_states(profile=None, limit=25):
    """Refresh recent Resend-accepted messages without pretending API acceptance is delivery.

    Resend's email detail endpoint exposes ``last_event`` for sent/delivered/bounced/failed
    states. Network/provider failures are diagnostic only and never overwrite a known state.
    """
    profile=profile or active_profile()
    if not profile or outgoing_method(profile)!='resend' or not getattr(profile,'resend_api_key_enc',''):
        return {'checked':0,'updated':0}
    key=decrypt(profile.resend_api_key_enc)
    if not key:
        return {'checked':0,'updated':0}
    qs=MailEvent.objects.filter(kind='notification',delivery_status='accepted',metadata__provider='resend').exclude(message_id='').order_by('-occurred_at')[:max(1,min(100,int(limit or 25)))]
    checked=updated=0; errors=[]
    mapping={'delivered':'delivered','bounced':'bounced','failed':'failed','canceled':'rejected','cancelled':'rejected','complained':'rejected'}
    for event in qs:
        checked+=1
        try:
            r=requests.get(f'{RESEND_ENDPOINT}/{event.message_id}',headers={'Authorization':f'Bearer {key}','User-Agent':'ScoutBox/0.10.103'},timeout=10)
            if r.status_code<200 or r.status_code>=300:
                errors.append(f'{event.message_id}: HTTP {r.status_code}')
                continue
            data=r.json() if r.content else {}
            provider_state=str((data or {}).get('last_event') or '').strip().lower()
            new_state=mapping.get(provider_state)
            meta=dict(event.metadata or {}); meta['provider_last_event']=provider_state; meta['provider_checked_at']=timezone.now().isoformat()
            fields=['metadata']
            event.metadata=meta
            if new_state and new_state!=event.delivery_status:
                event.delivery_status=new_state; fields.append('delivery_status'); updated+=1
            event.save(update_fields=fields)
        except Exception as exc:
            errors.append(str(exc)[:180])
    return {'checked':checked,'updated':updated,'errors':errors[:5]}
