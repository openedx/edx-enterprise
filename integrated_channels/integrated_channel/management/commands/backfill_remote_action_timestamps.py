"""
Backfill the new remote_created_at and remote_updated_at content audit record values.
"""
from django.apps import apps
from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db.models import Q

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.logger import get_integrated_channels_logger
from integrated_channels.utils import batch_by_pk

User = auth.get_user_model()

LOGGER = get_integrated_channels_logger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Update content transmission items to have the new remote_created_at and remote_updated_at values.

    ./manage.py lms backfill_remote_action_timestamps
    """

    def handle(self, *args, **options):
        """
        Update all past content transmission items remote_created_at and remote_updated_at
        """

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        no_remote_created_at = Q(remote_created_at__isnull=True)
        for items_batch in batch_by_pk(ContentMetadataItemTransmission, extra_filter=no_remote_created_at):
            for item in items_batch:
                try:
                    item.remote_created_at = item.created
                    item.remote_updated_at = item.modified
                    item.save()
                    message = f'ContentMetadataItemTransmission <{item.id}> ' \
                        f'remote_created_at={item.remote_created_at}, ' \
                        f'remote_updated_at={item.remote_updated_at}'
                    LOGGER.info(msg=message, extra={
                        'channel_name': item.integrated_channel_code,
                        'enterprise_customer_uuid': item.enterprise_customer.uuid,
                        'course_or_course_run_key': item.content_id,
                    })
                except Exception:  # pylint: disable=broad-except
                    message = f'ContentMetadataItemTransmission <{item.id}> ' \
                        f'error backfilling remote_created_at & remote_updated_at'
                    LOGGER.exception(msg=message, extra={
                        'channel_name': item.integrated_channel_code,
                        'enterprise_customer_uuid': item.enterprise_customer.uuid,
                        'course_or_course_run_key': item.content_id,
                    })
