from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
ALLOWED_HOSTS = [x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS','localhost,127.0.0.1,[::1]').split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if x.strip()]

INSTALLED_APPS = [
    'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
    'django.contrib.messages','django.contrib.staticfiles','portal.apps.PortalConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware','portal.middleware.FilterStateMiddleware','django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'opportunity_portal.urls'
TEMPLATES = [{
    'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],
    'APP_DIRS':True,'OPTIONS':{'context_processors':[
        'django.template.context_processors.request','django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages','portal.context_processors.portal_meta',
    ]}
}]
WSGI_APPLICATION='opportunity_portal.wsgi.application'
if os.getenv('USE_SQLITE','0') == '1':
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'dev.sqlite3'}}
else:
    DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','opportunity_portal'),
        'USER':os.getenv('POSTGRES_USER','portal'),'PASSWORD':os.getenv('POSTGRES_PASSWORD','portal-db-change-me'),
        'HOST':os.getenv('POSTGRES_HOST','db'),'PORT':os.getenv('POSTGRES_PORT','5432')}}
AUTH_PASSWORD_VALIDATORS=[]
LANGUAGE_CODE='en-us'; TIME_ZONE=os.getenv('PORTAL_TIME_ZONE','Asia/Singapore'); USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[BASE_DIR/'portal'/'static']
MEDIA_URL='/media/'; MEDIA_ROOT=BASE_DIR/'media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/login/'; LOGIN_REDIRECT_URL='/'; LOGOUT_REDIRECT_URL='/login/'
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
CELERY_BROKER_URL=os.getenv('REDIS_URL','redis://redis:6379/0'); CELERY_RESULT_BACKEND=CELERY_BROKER_URL
# Keep the historical `celery` queue as ScoutBox's background/default lane so any
# jobs published by older releases remain consumable after an upgrade. Long-running
# campaign discovery is routed to a dedicated queue/worker and can no longer occupy
# both background worker slots.
CELERY_TASK_DEFAULT_QUEUE='celery'
CELERY_TASK_ROUTES={
    'portal.tasks.run_campaign_job': {'queue':'discovery'},
}
# A worker should reserve only the task it can actually start. With long AI/search
# jobs this prevents one process from hiding a backlog of work from the other lane.
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_TASK_CREATE_MISSING_QUEUES=True
CELERY_BEAT_SCHEDULE={
    'scheduler-tick': {'task':'portal.tasks.scheduler_tick','schedule':60.0},
    'mail-sync-tick': {'task':'portal.tasks.mail_sync_tick','schedule':300.0},
    'blog-click-sync': {'task':'portal.tasks.blog_click_sync','schedule':900.0},
    'daily-digest-tick': {'task':'portal.tasks.daily_digest_tick','schedule':300.0},
    'facebook-page-title-tick': {'task':'portal.tasks.facebook_page_title_tick','schedule':300.0},
    'tracking-article-title-tick': {'task':'portal.tasks.tracking_article_title_tick','schedule':900.0},
    'company-domain-refresh-tick': {'task':'portal.tasks.company_domain_refresh_tick','schedule':900.0},
    'retention-cleanup-tick': {'task':'portal.tasks.retention_cleanup_tick','schedule':86400.0},
}
PORTAL_VERSION=(BASE_DIR/'VERSION').read_text(encoding='utf-8').strip() if (BASE_DIR/'VERSION').is_file() else 'unknown'
PORTAL_LAST_MODIFIED = '2026-10-01 12:27:00'
PORTAL_SHORT_NAME=os.getenv('PORTAL_SHORT_NAME','ScoutBox')
PORTAL_LONG_NAME=os.getenv('PORTAL_LONG_NAME','Niche Opportunity Intelligence Portal')
_portal_copyright=os.getenv('PORTAL_COPYRIGHT','© 2026 ToughDev').strip()
PORTAL_COPYRIGHT='© 2026 ToughDev' if _portal_copyright in {'Copyright ToughDev 2026','© 2026 by ToughDev'} else _portal_copyright
OLLAMA_BASE_URL=os.getenv('OLLAMA_BASE_URL','http://host.docker.internal:11434')

SCOUTBOX_BASE_URL=os.getenv('SCOUTBOX_BASE_URL', f"http://localhost:{os.getenv('PORTAL_HOST_PORT','8989')}").rstrip('/')
