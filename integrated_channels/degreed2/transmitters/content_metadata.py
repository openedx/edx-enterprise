# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Degreed.
"""

from integrated_channels.degreed2.client import Degreed2APIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class Degreed2ContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Degreed2.
    """

    def __init__(self, enterprise_configuration, client=Degreed2APIClient):
        """
        Use the ``Degreed2APIClient`` for content metadata transmission to Degreed.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _prepare_items_for_transmission(self, channel_metadata_items):
        # similar to canvas, we can't create courses in bulk hence limiting to size 1
        # this of course only is accurate if transmission chunk size is 1
        return {
            'courses': [channel_metadata_items[0]],
        }
