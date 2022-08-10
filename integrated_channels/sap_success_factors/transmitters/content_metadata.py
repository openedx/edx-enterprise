"""
Class for transmitting content metadata to SuccessFactors.
"""

import logging

from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient

LOGGER = logging.getLogger(__name__)


class SapSuccessFactorsContentMetadataTransmitter(ContentMetadataTransmitter):
    """
    This transmitter transmits exported content metadata to SAPSF.
    """

    def __init__(self, enterprise_configuration, client=SAPSuccessFactorsAPIClient):
        """
        Use the ``SAPSuccessFactorsAPIClient`` for content metadata transmission to SAPSF.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def _transmit_action(self, content_metadata_item_map, client_method, action_name):
        """
        Set status to INACTIVE for items that should be deleted.
        """
        if action_name == 'delete':
            for _, item in content_metadata_item_map.items():
                LOGGER.info(f'_transmit_delete <{item.id}>')
                item.channel_metadata['status'] = 'INACTIVE'
                item.save()
        return super()._transmit_action(content_metadata_item_map, client_method, action_name)

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'ocnCourses': channel_metadata_items
        }
