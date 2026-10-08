import os

from django.core.management.base import BaseCommand

from portal.models import AIProviderConfig, BlogStatsConfig, EmailProfile, FacebookConfig
from portal.services.crypto import decrypt


def _value(value, empty='(not configured)'):
    if value is None:
        return empty
    value = str(value)
    return value if value else empty


def _yn(value):
    return 'yes' if value else 'no'


class Command(BaseCommand):
    help = (
        'Print currently stored portal integration credentials in plaintext. '
        'This is a local recovery/inspection command and its output contains live secrets.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-infrastructure',
            action='store_true',
            help='Also print PostgreSQL/Redis and selected application environment secrets.',
        )

    def section(self, title):
        self.stdout.write('')
        self.stdout.write('=' * 78)
        self.stdout.write(title)
        self.stdout.write('=' * 78)

    def line(self, label, value, indent='  '):
        self.stdout.write(f'{indent}{label}: {_value(value)}')

    def handle(self, *args, **opts):
        self.stderr.write(self.style.WARNING(
            'WARNING: this command prints decrypted credentials and authentication tokens. '
            'Do not paste its output into tickets/chat/logs and do not leave redirected output on disk.'
        ))

        self.section('Portal administrator')
        self.line('Configured admin email', os.getenv('PORTAL_ADMIN_EMAIL', 'admin@portal.test'))
        self.line('Password', '(not retrievable: Django stores a one-way password hash; use ./reset_admin_password.sh)')

        self.section('Saved mail profiles')
        profiles = list(EmailProfile.objects.order_by('-active', 'template'))
        if not profiles:
            self.stdout.write('  (no EmailProfile records found)')
        for p in profiles:
            self.stdout.write(f'  [{p.get_template_display()}] active={_yn(p.active)}')
            self.line('IMAP host', p.imap_host, '    ')
            self.line('IMAP port', p.imap_port, '    ')
            self.line('IMAP SSL', _yn(p.imap_ssl), '    ')
            self.line('IMAP email', p.imap_email, '    ')
            self.line('IMAP username', p.imap_username, '    ')
            self.line('IMAP password', decrypt(p.imap_password_enc), '    ')
            self.line('Inbox folder', p.inbox_folder, '    ')
            self.line('Drafts folder', p.drafts_folder, '    ')
            self.line('Sent folder', p.sent_folder, '    ')
            method = 'resend' if p.template == 'external' and p.outgoing_method == 'resend' else 'smtp'
            self.line('Outgoing service', 'Resend API' if method == 'resend' else 'SMTP', '    ')
            if method == 'resend':
                self.line('Resend API endpoint', 'https://api.resend.com/emails', '    ')
                self.line('Resend API key', decrypt(p.resend_api_key_enc), '    ')
            else:
                self.line('SMTP host', p.smtp_host, '    ')
                self.line('SMTP port', p.smtp_port, '    ')
                self.line('SMTP TLS', _yn(p.smtp_tls), '    ')
                self.line('SMTP username', p.smtp_username, '    ')
                self.line('SMTP password', decrypt(p.smtp_password_enc), '    ')
            self.line('Notification From name', p.notification_from_name, '    ')
            self.line('Notification From email', p.notification_from_email, '    ')

        self.section('Internal development mail services (container environment)')
        self.line('Mailpit UI URL', 'http://localhost:8025/')
        self.line('Mailpit UI username', os.getenv('MAILPIT_UI_USER', 'mailpit'))
        self.line('Mailpit UI password', os.getenv('MAILPIT_UI_PASSWORD', 'mailpit-demo'))
        self.line('Mailpit SMTP host', os.getenv('MAILPIT_SMTP_HOST', 'mailpit'))
        self.line('Mailpit SMTP port', os.getenv('MAILPIT_SMTP_PORT', '1025'))
        self.line('Mailpit SMTP username', os.getenv('MAILPIT_SMTP_USER', 'portal-smtp'))
        self.line('Mailpit SMTP password', os.getenv('MAILPIT_SMTP_PASSWORD', 'portal-smtp-demo'))
        self.line('GreenMail IMAP email', os.getenv('DEV_IMAP_EMAIL', 'candidate@application.test'))
        self.line('GreenMail IMAP username', os.getenv('DEV_IMAP_USER', 'candidate@application.test'))
        self.line('GreenMail IMAP password', os.getenv('DEV_IMAP_PASSWORD', 'candidate-imap-demo'))
        self.line('GreenMail IMAP host', os.getenv('DEV_IMAP_HOST', 'greenmail'))
        self.line('GreenMail IMAP port', os.getenv('DEV_IMAP_PORT', '3143'))

        self.section('AI provider credentials')
        providers = list(AIProviderConfig.objects.order_by('provider'))
        if not providers:
            self.stdout.write('  (no AI provider records found)')
        for cfg in providers:
            self.stdout.write(f'  [{cfg.get_provider_display()}] enabled={_yn(cfg.enabled)}')
            self.line('Base URL', cfg.base_url, '    ')
            self.line('Default model', cfg.default_model, '    ')
            if cfg.provider == 'ollama':
                self.line('API key', '(not required for normal local Ollama)', '    ')
            else:
                self.line('API key', decrypt(cfg.api_key_enc), '    ')

        self.section('Search/API credentials')
        self.line('Brave Search API key', os.getenv('BRAVE_SEARCH_API_KEY', ''))

        self.section('Facebook / Meta authentication')
        fb = FacebookConfig.objects.filter(pk=1).first()
        stored_token = decrypt(fb.graph_access_token_enc) if fb else ''
        effective_token = stored_token or os.getenv('META_ACCESS_TOKEN', '')
        self.line('Graph API enabled', _yn(fb.use_graph_api) if fb else '(no saved FacebookConfig record)')
        self.line('Stored Graph access token', stored_token)
        if not stored_token:
            self.line('Effective Graph token from environment', effective_token)
        saved_page_ids = fb.graph_page_ids if fb else ''
        self.line('Graph Page IDs (saved)', saved_page_ids)
        if not saved_page_ids:
            self.line('Graph Page IDs (environment)', os.getenv('META_PAGE_IDS', ''))
        self.line('Authenticated browser cookie header', decrypt(fb.cookie_header_enc) if fb else '')
        self.line('Meta Graph API version', os.getenv('META_GRAPH_VERSION', 'v23.0'))

        self.section('External statistics connector')
        blog = BlogStatsConfig.objects.filter(pk=1).first()
        self.line('Enabled', _yn(blog.enabled) if blog else '(not initialized)')
        self.line('Credentials', 'Stored in the private sidecar runtime configuration; not printed by ScoutBox')

        if opts['include_infrastructure']:
            self.section('Infrastructure/application environment (optional)')
            self.line('PostgreSQL host', os.getenv('POSTGRES_HOST', 'db'))
            self.line('PostgreSQL port', os.getenv('POSTGRES_PORT', '5432'))
            self.line('PostgreSQL database', os.getenv('POSTGRES_DB', 'opportunity_portal'))
            self.line('PostgreSQL username', os.getenv('POSTGRES_USER', 'portal'))
            self.line('PostgreSQL password', os.getenv('POSTGRES_PASSWORD', ''))
            self.line('Redis URL', os.getenv('REDIS_URL', 'redis://redis:6379/0'))
            self.line('Django secret key', os.getenv('DJANGO_SECRET_KEY', ''))
            self.line('Portal Fernet key', os.getenv('PORTAL_FERNET_KEY', '') or '(derived from Django secret key)')

        self.stdout.write('')
        self.stderr.write(self.style.WARNING(
            'Credential dump complete. If you redirected this output to a file, protect or delete that file immediately.'
        ))
