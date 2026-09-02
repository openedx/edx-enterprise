"""
Deletes records from the IntegratedChannelAPIRequestLogs model that are older than one month..
"""
from datetime import timedelta
from logging import getLogger

from django.contrib import auth
from django.core.management.base import BaseCommand
from django.utils import timezone
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

    def add_arguments(self, parser):
        """
        Adds custom arguments to the parser.
        """
        parser.add_argument('time_duration', nargs='?', type=int, default=30,
                            help='The duration in days for deleting old records. Default is 30 days.')

    def handle(self, *args, **options):
        """
        Remove the duplicated transmission audit records for integration channels.
        """
        time_duration = options['time_duration']
        time_threshold = timezone.now() - timedelta(days=time_duration)
        deleted_count, _ = integrated_channel_request_log_model().objects.filter(created__lt=time_threshold).delete()

        LOGGER.info(f"Deleting records from IntegratedChannelAPIRequestLogs. Total records to delete: {deleted_count}")
