"""
Mark all content metadata audit records not directly connected to a customer's catalogs as orphaned.
"""
import logging

from django.core.management.base import BaseCommand

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import mark_orphaned_content_metadata_audit

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Mark all content metadata audit records not directly connected to a customer's catalogs as orphaned.

    ./manage.py lms mark_orphaned_content_metadata_audits
    """

    def handle(self, *args, **options):
        """
        Mark all content metadata audit records not directly connected to a customer's catalogs as orphaned.
        """
        try:
            mark_orphaned_content_metadata_audit.delay()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f'Failed to mark orphaned content metadata audits. Task failed with exception: {exc}')
