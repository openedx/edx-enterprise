# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Cornerstone.
"""
from itertools import islice

from django.conf import settings

from integrated_channels.cornerstone.client import CornerstoneAPIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.utils import chunks


class CornerstoneContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter prepares content metadata to be consumed by Cornerstone.
    """

    def __init__(self, enterprise_configuration, client=CornerstoneAPIClient):
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Placeholder
        """
        items_to_create, items_to_update, items_to_delete, transmission_map = self._partition_items(payload)
        self._transmit_delete(items_to_delete)
        self._transmit_create(items_to_create)
        self._transmit_update(items_to_update, transmission_map)
        return self._prepare_items_for_transmission(payload)

    def _transmit_create(self, channel_metadata_item_map):
        """
        Placeholder
        """
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        create_chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        for chunk in islice(create_chunk_items, transmission_limit):
            self._create_transmissions(chunk)

    def _transmit_update(self, channel_metadata_item_map, transmission_map):
        """
        Placeholder
        """
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        update_chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        for chunk in islice(update_chunk_items, transmission_limit):
            self._update_transmissions(chunk, transmission_map)

    def _transmit_delete(self, channel_metadata_item_map):
        """
        Placeholder
        """
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        delete_chunk_items = chunks(channel_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        for chunk in islice(delete_chunk_items, transmission_limit):
            self._delete_transmissions(chunk.keys())

    def _prepare_items_for_transmission(self, channel_metadata_items):
        course_list = [
            item.channel_metadata
            for item in channel_metadata_items.values()
        ]
        return course_list
