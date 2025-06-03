"""
Base settings for enterprise app.
"""

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'create-enterprise-customer-admins': {
        'task': 'enterprise.tasks.create_enterprise_customer_admins_task',
        'schedule': 3600.0,  # Run every hour
        'args': (500, False),  # (batch_size, dry_run)
    },
} 