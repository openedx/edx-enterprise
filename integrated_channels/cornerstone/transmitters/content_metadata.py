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

    def _transmit_action(self, content_metadata_item_map, client_method, action_name):
        """
        Set status to IsActive to False for items that should be deleted.
        """
        if action_name == 'delete':
            for _, item in content_metadata_item_map.items():
                item.channel_metadata['IsActive'] = False
                item.save()
        return super()._transmit_action(content_metadata_item_map, client_method, action_name)
