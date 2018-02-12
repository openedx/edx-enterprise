# -*- coding: utf-8 -*-
"""
Generic content metadata transmitter for integrated channels.
"""

from __future__ import absolute_import, unicode_literals

import json
import logging

from jsondiff import diff

from integrated_channels.exceptions import ClientError
from integrated_channels.utils import chunks
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from requests import RequestException

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist


LOGGER = logging.getLogger(__name__)


class ContentMetadataTransmitter(Transmitter):
    """
    Used to transmit content metadata to an integrated channel.
    """

    def __init__(self, enterprise_configuration, client=IntegratedChannelApiClient):
        """
        By default, use the abstract integrated channel API client which raises an error when used if not subclassed.
        """
        super(ContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, content_metadata_item_exports):
        """
        Transmit content metadata items to the integrated channel.
        """
        items_to_delete = {}
        transmission_map = {}
        export_aggregation_keys = content_metadata_item_exports.keys()
        for t in self._get_transmissions():
            transmission_map[t.aggregation_key] = t.channel_metadata
            if t.aggregation_key not in export_aggregation_keys:
                items_to_delete[t.aggregation_key] = t.channel_metadata

        self._transmit_delete(items_to_delete)

        items_to_create = {}
        items_to_update = {}
        for item in content_metadata_item_exports.values():
            aggregation_key = item.aggregation_key
            channel_metadata = item.channel_metadata
            transmitted_item = transmission_map.get(aggregation_key)
            if transmitted_item:
                if diff(channel_metadata, transmitted_item):
                    items_to_update[aggregation_key] = channel_metadata
            else:
                items_to_create[aggregation_key] = channel_metadata

        self._transmit_create(items_to_create)
        self._transmit_update(items_to_update, transmission_map)

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return channel_metadata_items

    def _serialize_items_for_create(self, channel_metadata_items):
        return json.dumps(
            self._prepare_items_for_transmission(channel_metadata_items),
            sort_keys=True
        ).encode('utf-8')

    def _serialize_items_for_update(self, channel_metadata_items):
        return json.dumps(
            self._prepare_items_for_transmission(channel_metadata_items),
            sort_keys=True
        ).encode('utf-8')

    def _serialize_items_for_delete(self, channel_metadata_items):
        return json.dumps(
            self._prepare_items_for_transmission(channel_metadata_items),
            sort_keys=True
        ).encode('utf-8')

    def _transmit_create(self, channel_metadata_item_map):
        for chunk in chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size):
            serialized_chunk = self._serialize_items_for_create(chunk.values())
            try:
                self.client.create_content_metadata(serialized_chunk)
            except ClientError as e:
                LOGGER.error(e)
                LOGGER.error(
                    'Failed to create integrated channel content metadata items for [%s] [%s]: [%s]',
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code,
                    chunk.keys()
                )
            else:
                self._create_transmissions(chunk)

    def _transmit_update(self, channel_metadata_item_map, transmission_map):
        for chunk in chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size):
            serialized_chunk = self._serialize_items_for_create(chunk.values())
            try:
                self.client.update_content_metadata(serialized_chunk)
            except ClientError as e:
                LOGGER.error(e)
                LOGGER.error(
                    'Failed to update integrated channel content metadata items for [%s] [%s]: [%s]',
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code,
                    chunk.keys()
                )
            else:
                for aggregation_key, channel_metadata in chunk.items():
                    transmission = transmission_map[aggregation_key]
                    transmission.channel_metadata = channel_metadata
                    transmission.save()

    def _transmit_delete(self, channel_metadata_item_map):
        for chunk in chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size):
            serialized_chunk = self._serialize_items_for_delete(chunk.values())
            try:
                self.client.delete_content_metadata(serialized_chunk)
            except ClientError as e:
                LOGGER.error(e)
                LOGGER.error(
                    'Failed to delete integrated channel content metadata items for [%s] [%s]: [%s]',
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.channel_code,
                    chunk.keys()
                )
            else:
                self._delete_transmissions(chunk.keys())

    def _get_transmissions(self):
        ContentMetadataItemTransmission = apps.get_model('ContentMetadataItemTransmission')
        return ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code
        )

    def _create_transmissions(self, content_metadata_item_map):
        ContentMetadataItemTransmission = apps.get_model('ContentMetadataItemTransmission')
        transmissions = []
        for aggregation_key, channel_metadata in content_metadata_item_map.items():
            transmissions.append(
                ContentMetadataItemTransmission(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    integrated_channel_code=self.enterprise_configuration.channel_code,
                    aggregation_key=aggregation_key,
                    channel_metadata=channel_metadata
                )
            )
        ContentMetadataItemTransmission.objects.bulk_create(transmissions)

    def _delete_transmissions(self, content_metadata_item_aggregation_keys):
        ContentMetadataItemTransmission = apps.get_model('ContentMetadataItemTransmission')
        ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code,
            aggregation_key__in=content_metadata_item_aggregation_keys
        ).delete()
