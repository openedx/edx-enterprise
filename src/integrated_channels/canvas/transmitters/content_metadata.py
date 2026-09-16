"""
Transmitter for Canvas content metadata
"""

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class CanvasContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Canvas.
    """

    def __init__(self, enterprise_configuration, client=CanvasAPIClient):
        """
        Use the ``CanvasAPIClient`` for content metadata transmission to Canvas.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _prepare_items_for_transmission(self, channel_metadata_items):
        # here is a hack right now to send only one item
        # we have to investigate how to handle multiple
        # metadata items
        return {
            'course': channel_metadata_items[0],
        }
