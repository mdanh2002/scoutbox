import os
from celery import Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opportunity_portal.settings')
app = Celery('opportunity_portal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
