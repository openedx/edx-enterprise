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

    def transmit(self, create_payload, update_payload, delete_payload):
        """
        Dummy transmit method overriding base transmissions, intended to cause any normal invocations of the Cornerstone
        transmitter to result in a NOOP because Cornerstone is a pull based system and as such shouldn't send (push)
        information like other channels
        """
        self._log_info(
            f"Cornerstone base transmission invoked for config: {self.enterprise_configuration.id}. Treating as a NOOP"
        )
        pass  # pylint: disable=unnecessary-pass

    def transmit_for_web(self, create_payload, update_payload, delete_payload):
        """
        Alternative method to invoke a transmission for a Cornerstone channel.
        """
        return super().transmit(
            create_payload=create_payload, update_payload=update_payload, delete_payload=delete_payload
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
