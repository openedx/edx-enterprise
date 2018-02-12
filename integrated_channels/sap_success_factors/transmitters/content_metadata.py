# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

import json
import logging

from integrated_channels.exceptions import ClientError
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
        super(SapSuccessFactorsContentMetadataTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Transmit content metadata items to the integrated channel.
        """
        items_to_create, items_to_update, items_to_delete, transmission_map = self._partition_items(payload)
        serialized_items = self._serialize_items(
            list(items_to_create.values()),
            list(items_to_update.values()),
            list(items_to_delete.values())
        )
        try:
            self.client.update_content_metadata(serialized_items)
        except ClientError as exc:
            LOGGER.error(exc)
            LOGGER.error(
                'Failed to update integrated channel content metadata items for [%s] [%s]: [%s]',
                self.enterprise_configuration.enterprise_customer.name,
                self.enterprise_configuration.channel_code,
                serialized_items
            )
        else:
            self._create_transmissions(items_to_create)
            self._update_transmissions(items_to_update, transmission_map)
            self._delete_transmissions(items_to_delete.keys())

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'ocnCourses': channel_metadata_items
        }

    def _serialize_items(self, items_to_create, items_to_update, items_to_delete):
        """
        Serialize content metadata items for transmission to SAP SuccessFactors.
        """
        for item in items_to_delete:
            item['status'] = 'INACTIVE'

        return json.dumps(
            self._prepare_items_for_transmission(items_to_create + items_to_update + items_to_delete),
            sort_keys=True
        ).encode('utf-8')
