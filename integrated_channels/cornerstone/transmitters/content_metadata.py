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
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
