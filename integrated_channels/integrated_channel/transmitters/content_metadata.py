# -*- coding: utf-8 -*-
"""
Generic content metadata transmitter for integrated channels.
"""

import json
import logging
from itertools import islice

from jsondiff import diff

from django.apps import apps
from django.conf import settings

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from integrated_channels.utils import chunks

LOGGER = logging.getLogger(__name__)


class ContentMetadataTransmitter(Transmitter):
    """
    Used to transmit content metadata to an integrated channel.
    """

    def __init__(self, enterprise_configuration, client=IntegratedChannelApiClient):
        """
        By default, use the abstract integrated channel API client which raises an error when used if not subclassed.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Transmit content metadata items to the integrated channel.
        """
        items_to_create, items_to_update, items_to_delete, transmission_map = self._partition_items(payload)
        self._transmit_delete(items_to_delete)
        self._transmit_create(items_to_create)
        self._transmit_update(items_to_update, transmission_map)

    def _partition_items(self, channel_metadata_item_map):
        """
        Return items that need to be created, updated, and deleted along with the
        current ContentMetadataItemTransmissions.
        """
        items_to_create = {}
        items_to_update = {}
        items_to_delete = {}
        transmission_map = {}
        export_content_ids = channel_metadata_item_map.keys()

        # Get the items that were previously transmitted to the integrated channel.
        # If we are not transmitting something that was previously transmitted,
        # we need to delete it from the integrated channel.
        for transmission in self._get_transmissions():
            transmission_map[transmission.content_id] = transmission
            if transmission.content_id not in export_content_ids:
                items_to_delete[transmission.content_id] = transmission.channel_metadata

        # Compare what is currently being transmitted to what was transmitted
        # previously, identifying items that need to be created or updated.
        for item in channel_metadata_item_map.values():
            content_id = item.content_id
            channel_metadata = item.channel_metadata
            transmitted_item = transmission_map.get(content_id, None)
            if transmitted_item is not None:
                if diff(channel_metadata, transmitted_item.channel_metadata):
                    items_to_update[content_id] = channel_metadata
            else:
                items_to_create[content_id] = channel_metadata

        LOGGER.info(
            'Preparing to transmit creation of [%s] content metadata items with plugin configuration [%s]: [%s]',
            len(items_to_create),
            self.enterprise_configuration,
            list(items_to_create.keys()),
        )
        LOGGER.info(
            'Preparing to transmit update of [%s] content metadata items with plugin configuration [%s]: [%s]',
            len(items_to_update),
            self.enterprise_configuration,
            list(items_to_update.keys()),
        )
        LOGGER.info(
            'Preparing to transmit deletion of [%s] content metadata items with plugin configuration [%s]: [%s]',
            len(items_to_delete),
            self.enterprise_configuration,
            list(items_to_delete.keys()),
        )

        return items_to_create, items_to_update, items_to_delete, transmission_map

    def _prepare_items_for_transmission(self, channel_metadata_items):
        """
        Perform any necessary modifications to content metadata item
        data structure before transmission. This can be overridden by
        subclasses to add any data structure wrappers expected by the
        integrated channel.
        """
        return channel_metadata_items

    def _serialize_items(self, channel_metadata_items):
        """
        Serialize content metadata items for a create transmission to the integrated channel.
        """
        return json.dumps(
            self._prepare_items_for_transmission(channel_metadata_items),
            sort_keys=True
        ).encode('utf-8')

    def _transmit_create(self, channel_metadata_item_map):
        """
        Transmit content metadata creation to integrated channel.
        """
        chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.create_content_metadata(serialized_chunk)
            except ClientError as exc:
                LOGGER.error(
                    'Failed to create [%s] content metadata items for integrated channel [%s] [%s]. '
                    'Task failed with message [%s] and status code [%s]',
                    len(chunk),
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code(),
                    exc.message,
                    exc.status_code
                )
                LOGGER.exception(exc)
            else:
                self._create_transmissions(chunk)

    def _transmit_update(self, channel_metadata_item_map, transmission_map):
        """
        Transmit content metadata update to integrated channel.
        """
        chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.update_content_metadata(serialized_chunk)
            except ClientError as exc:
                LOGGER.error(
                    'Failed to update [%s] content metadata items for integrated channel [%s] [%s]. '
                    'Task failed with message [%s] and status code [%s]',
                    len(chunk),
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code(),
                    exc.message,
                    exc.status_code
                )
                LOGGER.exception(exc)
            else:
                self._update_transmissions(chunk, transmission_map)

    def _transmit_delete(self, channel_metadata_item_map):
        """
        Transmit content metadata deletion to integrated channel.
        """
        chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.delete_content_metadata(serialized_chunk)
            except ClientError as exc:
                LOGGER.error(
                    'Failed to delete [%s] content metadata items for integrated channel [%s] [%s]. '
                    'Task failed with message [%s] and status code [%s]',
                    len(chunk),
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code(),
                    exc.message,
                    exc.status_code
                )
                LOGGER.exception(exc)
            else:
                self._delete_transmissions(chunk.keys())

    def _get_transmissions(self):
        """
        Return the ContentMetadataItemTransmission models for previously
        transmitted content metadata items.
        """
        # pylint: disable=invalid-name
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        return ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code()
        )

    def _create_transmissions(self, content_metadata_item_map):
        """
        Create ContentMetadataItemTransmission models for the given content metadata items.
        """
        # pylint: disable=invalid-name
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        transmissions = []
        for content_id, channel_metadata in content_metadata_item_map.items():
            transmissions.append(
                ContentMetadataItemTransmission(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    integrated_channel_code=self.enterprise_configuration.channel_code(),
                    content_id=content_id,
                    channel_metadata=channel_metadata
                )
            )
        ContentMetadataItemTransmission.objects.bulk_create(transmissions)

    def _update_transmissions(self, content_metadata_item_map, transmission_map):
        """
        Update ContentMetadataItemTransmission models for the given content metadata items.
        """
        for content_id, channel_metadata in content_metadata_item_map.items():
            transmission = transmission_map[content_id]
            transmission.channel_metadata = channel_metadata
            transmission.save()

    def _delete_transmissions(self, content_metadata_item_ids):
        """
        Delete ContentMetadataItemTransmission models associated with the given content metadata items.
        """
        # pylint: disable=invalid-name
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code(),
            content_id__in=content_metadata_item_ids
        ).delete()
