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
        return {
            'courses': channel_metadata_items,
            'orgCode': self.enterprise_configuration.degreed_company_id,
            'providerCode': self.enterprise_configuration.provider_id,
        }
