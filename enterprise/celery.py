"""
Celery app configuration for the enterprise application.
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise.settings')

app = Celery('enterprise')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-admin-invite-reminders': {
        'task': 'enterprise.tasks.send_enterprise_admin_invite_reminders',
        'schedule': crontab(),  # every minute
        'args': [],
    },
}
