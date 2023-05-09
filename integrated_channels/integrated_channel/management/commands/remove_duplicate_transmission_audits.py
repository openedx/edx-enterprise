"""
Remove duplicate transmission audits, keeping the most recently modified one.
"""
import logging

from django.core.management.base import BaseCommand

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import remove_duplicate_transmission_audits

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Iterate through all transmission audits and remove duplicates, keeping the most recently modified one.

    ./manage.py lms remove_duplicate_transmission_audits
    """

    def handle(self, *args, **options):
        """
        Iterate through all transmission audits and remove duplicates, keeping the most recently modified one.
        """
        try:
            LOGGER.info("Starting remove duplicate transmission audits management task.")
            remove_duplicate_transmission_audits.delay()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f'Failed to remove duplicate content metadata audits. Task failed with exception: {exc}')
