"""
Deletes records from the IntegratedChannelAPIRequestLogs model that are older than one month..
"""
from logging import getLogger
from datetime import timedelta
from django.utils import timezone

from django.contrib import auth
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from integrated_channels.utils import integrated_channel_request_log_model

User = auth.get_user_model()
LOGGER = getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to delete old records from the IntegratedChannelAPIRequestLogs model.
    """
    help = _('''
    This management command deletes records from the IntegratedChannelAPIRequestLogs model that are older than one month
    ''')

    def handle(self, *args, **options):
        """
        Remove the duplicated transmission audit records for integration channels.
        """
        one_month_ago = timezone.now() - timedelta(days=30)
        deleted_count, _ = integrated_channel_request_log_model().objects.filter(created__lt=one_month_ago).delete()

        LOGGER.info(f"Deleting records from IntegratedChannelAPIRequestLogs. Total records to delete: {deleted_count}")
