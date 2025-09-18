"""
Mark for re-send all CSOD content transmission with a remote_deleted_at but no api_response_status_code
"""
from django.apps import apps
from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db.models import Q

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.logger import get_integrated_channels_logger, log_with_context
from integrated_channels.utils import batch_by_pk

User = auth.get_user_model()

LOGGER = get_integrated_channels_logger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Mark for re-send all CSOD content transmission with a remote_deleted_at but no api_response_status_code

    ./manage.py lms reset_csod_remote_deleted_at
    """

    def handle(self, *args, **options):
        """
        Mark for re-send all CSOD content transmission with a remote_deleted_at
        """

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        csod_deleted_at = Q(
            integrated_channel_code='CSOD',
            remote_deleted_at__isnull=False
        )

        for items_batch in batch_by_pk(ContentMetadataItemTransmission, extra_filter=csod_deleted_at):
            for item in items_batch:
                try:
                    item.remote_deleted_at = None
                    item.save()
                    log_with_context(
                        LOGGER,
                        'INFO',
                        channel_name=item.integrated_channel_code,
                        enterprise_customer_uuid=item.enterprise_customer.uuid,
                        course_or_course_run_key=item.content_id,
                        message=f'integrated_channel_content_transmission_id={item.id}, '
                        'setting remote_deleted_at to None'
                    )
                except Exception:  # pylint: disable=broad-except
                    log_with_context(
                        LOGGER,
                        'EXCEPTION',
                        channel_name=item.integrated_channel_code,
                        enterprise_customer_uuid=item.enterprise_customer.uuid,
                        course_or_course_run_key=item.content_id,
                        message=f'integrated_channel_content_transmission_id={item.id}, '
                        'error setting remote_deleted_at to None'
                    )
