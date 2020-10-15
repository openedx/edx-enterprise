"""
Transmitter for Blackboard content metadata
"""

from integrated_channels.blackboard.client import BlackboardAPIClient
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter


class BlackboardContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to Canvas.
    """

    def __init__(self, enterprise_configuration, client=BlackboardAPIClient):
        """
        Use the ``BlackboardAPIClient`` for content metadata transmission.
        """
        super(BlackboardContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _prepare_items_for_transmission(self, channel_metadata_items):
        # here is a hack right now to send only one item
        # we have to investigate how to handle multiple
        # metadata items since there is no batch course create endpoint in blackboard
        return channel_metadata_items[0]
