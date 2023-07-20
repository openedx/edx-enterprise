"""
Class for transmitting content metadata to SuccessFactors.
"""
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient


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

    def transmit(self, create_payload, update_payload, delete_payload):
        """
        Transmit method overriding base transmissions. Due to rate limiting on SAP
        that prevents us from calling the post endpoint multiple times in one run,
        we prioritize the transmissions in DELETE, UPDATE, CREATE order
        """

        delete_payload_results, create_payload_results, update_payload_results = {}, {}, {}

        if delete_payload:
            self._log_info_for_each_item_map(delete_payload, 'transmitting delete')
            delete_payload_results = self._transmit_delete(delete_payload)
        elif update_payload:
            self._log_info_for_each_item_map(update_payload, 'transmitting update')
            update_payload_results = self._transmit_update(update_payload)
        elif create_payload:
            self._log_info_for_each_item_map(create_payload, 'transmitting create')
            create_payload_results = self._transmit_create(create_payload)
        return create_payload_results, update_payload_results, delete_payload_results

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'ocnCourses': channel_metadata_items
        }
