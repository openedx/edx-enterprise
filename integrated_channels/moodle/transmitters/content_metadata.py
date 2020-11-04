# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Moodle.
"""
import logging

from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.moodle.client import MoodleAPIClient

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

    def _prepare_items_for_transmission(self, channel_metadata_items):
        """
        Takes items from the exporter and formats the keys in the way required for
        course creation in Moodle.
        Note: It is *only* used for course creation, no other end point.
        """
        items = {}
        for _, item in enumerate(channel_metadata_items):
            for key in item:
                new_key = 'courses[0][{0}]'.format(key)
                items[new_key] = item[key]
                if key == 'announcement':
                    if 'announcements' not in items:
                        items['announcements'] = {}
                    items['announcements'][next(iter(item[key]))] = item[key][next(iter(item[key]))]
                else:
                    new_key = 'courses[{0}][{1}]'.format(index, key)
                    items[new_key] = item[key]

        return items

    def _prepare_items_for_update_transmission(self, channel_metadata_items):
        """
        updates use same format sort of.
        """
        items = {}
        for index, item in enumerate(channel_metadata_items):
            for key in item:
                if key != 'announcement':
                    new_key = 'courses[{0}][{1}]'.format(index, key)
                    items[new_key] = item[key]
        return items

    def _serialize_create_items(self, channel_metadata_items):
        """
        Overrides the base class to return an object and to use special prepare method.
        """
        return self._prepare_items_for_create_transmission(channel_metadata_items)

    def _serialize_update_items(self, channel_metadata_items):
        return self._prepare_items_for_update_transmission(channel_metadata_items)
