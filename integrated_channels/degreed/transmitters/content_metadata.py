# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to Degreed.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.degreed.client import DegreedAPIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class DegreedContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Degreed.
    """

    def __init__(self, enterprise_configuration, client=DegreedAPIClient):
        """
        Use the ``DegreedAPIClient`` for content metadata transmission to Degreed.
        """
        super(DegreedContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'courses': channel_metadata_items,
            'orgCode': self.enterprise_configuration.degreed_company_id,
            'providerCode': self.enterprise_configuration.provider_id,
        }
