"""
Remove content transmission audit records that do not contain a catalog UUID.
"""
import logging

from django.core.management.base import BaseCommand

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import remove_null_catalog_transmission_audits

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Remove content transmission audit records that do not contain a catalog UUID.
    ./manage.py lms remove_null_catalog_transmission_audits
    """

    def handle(self, *args, **options):
        """
        Filter content transmission audit records that do not contain a catalog UUID and remove them.
        """
        try:
            remove_null_catalog_transmission_audits.delay()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(
                f'''Failed to remove content transmission audits that do not
                contain a catalog UUID. Task failed with exception: {exc}'''
            )
