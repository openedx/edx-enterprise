# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Moodle.
"""
import logging
from itertools import islice
from time import sleep

from django.conf import settings

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.moodle.client import MoodleAPIClient
from integrated_channels.utils import chunks

# Based on averages and the default nginx url length limit,
# we might as well go to 1 if we hit a failure.
LOW_CHUNK_SIZE = 1

LOGGER = logging.getLogger(__name__)


class MoodleContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Moodle.
    """

    def __init__(self, enterprise_configuration, client=MoodleAPIClient):
        """
        Use the ``MoodleAPIClient`` for content metadata transmission to Moodle.
        """
        super(MoodleContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _transmit_create(self, channel_metadata_item_map, chunk_size=None, count=0):  # pylint: disable=arguments-differ
        """
        Transmit content metadata creation to integrated channel.
        """
        chunk_size = chunk_size if chunk_size else self.enterprise_configuration.transmission_chunk_size
        chunk_items = chunks(channel_metadata_item_map, chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.create_content_metadata(serialized_chunk)
            except ClientError as exc:
                if exc.status_code == 414 and count <= 1:
                    # On initial 414, we should retry after slight delay using our lowest chunk size.
                    # Since our lowest is currently 1, if we fail again,
                    # we just need to record the exception and give up.
                    sleep(5)
                    count += 1
                    self._transmit_create(channel_metadata_item_map, chunk_size=LOW_CHUNK_SIZE, count=count)
                else:
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

    def _transmit_update(self, channel_metadata_item_map, transmission_map, chunk_size=None, count=0):  # pylint: disable=arguments-differ
        """
        Transmit content metadata update to integrated channel.
        """
        chunk_size = chunk_size if chunk_size else self.enterprise_configuration.transmission_chunk_size
        chunk_items = chunks(channel_metadata_item_map, chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.update_content_metadata(serialized_chunk)
            except ClientError as exc:
                if exc.status_code == 414 and count <= 1:
                    count += 1
                    sleep(5)
                    self._transmit_update(
                        channel_metadata_item_map,
                        transmission_map,
                        chunk_size=LOW_CHUNK_SIZE,
                        count=count
                    )
                else:
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

    def _transmit_delete(self, channel_metadata_item_map, chunk_size=None, count=0):  # pylint: disable=arguments-differ
        """
        Transmit content metadata deletion to integrated channel.
        """
        chunk_size = chunk_size if chunk_size else self.enterprise_configuration.transmission_chunk_size
        chunk_items = chunks(channel_metadata_item_map, chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            serialized_chunk = self._serialize_items(list(chunk.values()))
            try:
                self.client.delete_content_metadata(serialized_chunk)
            except ClientError as exc:
                if exc.status_code == 414 and count <= 1:
                    count += 1
                    sleep(5)
                    self._transmit_delete(channel_metadata_item_map, chunk_size=LOW_CHUNK_SIZE, count=count)
                else:
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

    def _prepare_items_for_transmission(self, channel_metadata_items):
        """
        Takes items from the exporter and formats the keys in the way required for Moodle.
        """
        items = {}
        for index, item in enumerate(channel_metadata_items):
            for key in item:
                new_key = 'courses[{0}][{1}]'.format(index, key)
                items[new_key] = item[key]
        return items

    def _serialize_items(self, channel_metadata_items):
        """
        Overrides the base class _serialize_items method such that we return an object
        instead of a binary string.
        """
        return self._prepare_items_for_transmission(channel_metadata_items)
