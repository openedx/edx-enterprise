# -*- coding: utf-8 -*-
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

    def transmit(self, create_payload, update_payload, delete_payload, content_updated_mapping, **kwargs):
        """
        Prepare content metadata items for cornerstone API consumer. Update and create all necessary records before
        formatting the data for transmission.

        Args:
            create_payload (dict): Object mapping of content key to transformed channel metadata for transmitting a
                creation payload to the external LMS

            update_payload (dict): Object mapping of content key to updated content metadata transmission record for
                transmitting an update payload to the external LMS

            delete_payload (dict): Object mapping of content key to updated content metadata transmission record for
                transmitting a delete payload to the external LMS

            content_updated_mapping (dict): Mapping between content key to both catalog UUID and the content's last
                modified time
        """
        self._transmit_delete(delete_payload)
        self._transmit_create(create_payload, content_updated_mapping)
        self._transmit_update(update_payload)
        return self._prepare_update_and_create_items_for_transmission(create_payload, update_payload)

    def _transmit_create(self, channel_metadata_item_map, content_updated_mapping):
        """
        Generate the appropriate ContentMetadataItemTransmission objects according to the channel_metadata_item_map

        Args:
            channel_metadata_item_map (dict): A dictionary representation of the content to be created based on the
                exported content metadata.

            items_catalog_updated_times (dict): Mapping between content keys and the last updated time of the associated
                enterprise catalog and the catalog uuid
        """
        self._create_transmissions(channel_metadata_item_map, content_updated_mapping)

    def _transmit_update(self, update_payload):
        """
        Update the appropriate ContentMetadataItemTransmission objects according to the channel_metadata_item_map and
        transmission_map

        Args:
            update_payload (dict): Mapping between content keys and updated ContentMetadataItemTransmission record
        """
        updated_metadata_mapping = {key: item.channel_metadata for key, item in update_payload.items()}
        self._update_transmissions(update_payload, updated_metadata_mapping)

    def _transmit_delete(self, channel_metadata_item_map):
        """
        Remove the appropriate ContentMetadataItemTransmission objects according to the channel_metadata_item_map

        Args:
            channel_metadata_item_map (dict): A dictionary representation of the content to be removed based on the
                exported content metadata.
        """
        self._delete_transmissions(channel_metadata_item_map)

    def _prepare_update_and_create_items_for_transmission(self, create_payload, update_payload):
        """
        Format the content metadata to what CSOD consumers expect ie a singular list of content metadata items.
        """
        created_items_list = list(create_payload.values())
        updated_items_list = [item.channel_metadata for item in update_payload.values()]
        return created_items_list + updated_items_list
