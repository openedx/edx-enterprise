# -*- coding: utf-8 -*-
"""
Class for transmitting course metadata to Cornerstone.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.csod_web_services.client import CSODWebServicesAPIClient


class CSODWebServicesContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Cornerstone.
    """

    def __init__(self, enterprise_configuration, client=CSODWebServicesAPIClient):
        """
        Use the ``CSODWebServicesAPIClient`` for content metadata transmission to Cornerstone.
        """
        super(CSODWebServicesContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
