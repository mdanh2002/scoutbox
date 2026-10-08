import os
from django.core.management.base import BaseCommand
from portal.models import EmailProfile
from portal.services.crypto import encrypt


class Command(BaseCommand):
    help = 'Reset/activate the Internal Development mail profile (GreenMail IMAP + Mailpit SMTP) without erasing External Mail credentials.'

    def handle(self, *args, **opts):
        internal,_=EmailProfile.objects.get_or_create(template='internal')
        internal.imap_host=os.getenv('DEV_IMAP_HOST','greenmail')
        internal.imap_port=int(os.getenv('DEV_IMAP_PORT','3143'))
        internal.imap_ssl=False
        internal.imap_email=os.getenv('DEV_IMAP_EMAIL','candidate@application.test')
        internal.imap_username=os.getenv('DEV_IMAP_USER','candidate@application.test')
        internal.imap_password_enc=encrypt(os.getenv('DEV_IMAP_PASSWORD','candidate-imap-demo'))
        internal.inbox_folder='INBOX'; internal.sent_folder='Sent'; internal.drafts_folder='Drafts'
        internal.smtp_host=os.getenv('MAILPIT_SMTP_HOST','mailpit')
        internal.smtp_port=int(os.getenv('MAILPIT_SMTP_PORT','1025'))
        internal.smtp_tls=False
        internal.smtp_username=os.getenv('MAILPIT_SMTP_USER','portal-smtp')
        internal.smtp_password_enc=encrypt(os.getenv('MAILPIT_SMTP_PASSWORD','portal-smtp-demo'))
        internal.notification_from_name=os.getenv('NOTIFICATION_FROM_NAME','Application Portal')
        internal.notification_from_email=os.getenv('NOTIFICATION_FROM_EMAIL','portal@mailpit.test')
        internal.active=True; internal.save()
        EmailProfile.objects.exclude(pk=internal.pk).update(active=False)
        self.stdout.write(self.style.SUCCESS('Internal Development mail profile reset and activated.'))
        self.stdout.write(f'IMAP: {internal.imap_email} @ {internal.imap_host}:{internal.imap_port}')
        self.stdout.write(f'Notification SMTP: {internal.notification_from_email} via {internal.smtp_host}:{internal.smtp_port}')
        self.stdout.write('External Mail profile credentials were preserved; only the active profile was switched back to Internal Development.')
