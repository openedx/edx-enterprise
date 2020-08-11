"""
Transmitter for Canvas content metadata
"""

from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class CanvasContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Canvas.
    """

    def __init__(self, enterprise_configuration): # TODO: , client=CanvasAPIClient
        """
        Use the ``CanvasAPIClient`` for content metadata transmission to Canvas.
        """
        super(CanvasContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            # TODO: client=client
        )

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'course': channel_metadata_items,
        }
