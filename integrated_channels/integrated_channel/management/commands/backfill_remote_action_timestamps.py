"""
Backfill the new remote_created_at and remote_updated_at content audit record values.
"""
import logging

from django.apps import apps
from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db.models import Q

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.utils import generate_formatted_log

User = auth.get_user_model()

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Update content transmission items to have the new remote_created_at and remote_updated_at values.

    ./manage.py lms backfill_remote_action_timestamps
    """

    def batch_by_pk(self, ModelClass, extra_filter=Q(), batch_size=10000):
        """
        using limit/offset does a lot of table scanning to reach higher offsets
        this scanning can be slow on very large tables
        if you order by pk, you can use the pk as a pivot rather than offset
        this utilizes the index, which is faster than scanning to reach offset
        """
        qs = ModelClass.objects.filter(extra_filter).order_by('pk')[:batch_size]
        while qs.exists():
            yield qs
            # qs.last() doesn't work here because we've already sliced
            # loop through so we eventually grab the last one
            for item in qs:
                start_pk = item.pk
            qs = ModelClass.objects.filter(pk__gt=start_pk).filter(extra_filter).order_by('pk')[:batch_size]

    def handle(self, *args, **options):
        """
        Update all past content transmission items remote_created_at and remote_updated_at
        """

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        no_remote_created_at = Q(remote_created_at__isnull=True)
        for items_batch in self.batch_by_pk(ContentMetadataItemTransmission, extra_filter=no_remote_created_at):
            for item in items_batch:
                try:
                    item.remote_created_at = item.created
                    item.remote_updated_at = item.modified
                    item.save()
                    LOGGER.info(generate_formatted_log(
                        item.integrated_channel_code,
                        item.enterprise_customer.uuid,
                        None,
                        item.content_id,
                        f'ContentMetadataItemTransmission <{item.id}> '
                        f'remote_created_at={item.remote_created_at}, '
                        f'remote_updated_at={item.remote_updated_at}'
                    ))
                except Exception:  # pylint: disable=broad-except
                    LOGGER.exception(generate_formatted_log(
                        item.integrated_channel_code,
                        item.enterprise_customer.uuid,
                        None,
                        item.content_id,
                        f'ContentMetadataItemTransmission <{item.id}> '
                        'error backfilling remote_created_at & remote_updated_at'
                    ))
