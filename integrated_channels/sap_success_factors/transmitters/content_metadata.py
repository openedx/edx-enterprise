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

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'ocnCourses': channel_metadata_items
        }
