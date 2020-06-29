# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Cornerstone.
"""

from integrated_channels.cornerstone.client import CornerstoneAPIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class CornerstoneContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter prepares content metadata to be consumed by Cornerstone.
    """

    def __init__(self, enterprise_configuration, client=CornerstoneAPIClient):
        super(CornerstoneContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Prepare content metadata items for cornerstone API consumer.
        """
        return self._prepare_items_for_transmission(payload)

    def _prepare_items_for_transmission(self, channel_metadata_items):
        course_list = [
            item.channel_metadata
            for item in channel_metadata_items.values()
        ]
        return course_list
