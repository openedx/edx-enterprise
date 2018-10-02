# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

import logging

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.utils import chunks

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
        self._prepare_items_for_delete(items_to_delete)
        prepared_items = {}
        prepared_items.update(items_to_create)
        prepared_items.update(items_to_update)
        prepared_items.update(items_to_delete)

        skip_metadata_transmission = False

        for chunk in chunks(prepared_items, self.enterprise_configuration.transmission_chunk_size):
            chunked_items = list(chunk.values())
            if skip_metadata_transmission:
                # Remove the failed items from the create/update/delete dictionaries,
                # so ContentMetadataItemTransmission objects are not synchronized for
                # these items below.
                self._remove_failed_items(chunked_items, items_to_create, items_to_update, items_to_delete)
            else:
                try:
                    self.client.update_content_metadata(self._serialize_items(chunked_items))
                except ClientError as exc:
                    LOGGER.error(
                        'Failed to update [%s] content metadata items for integrated channel [%s] [%s]',
                        len(chunked_items),
                        self.enterprise_configuration.enterprise_customer.name,
                        self.enterprise_configuration.channel_code,
                    )
                    LOGGER.error(exc)

                    # Remove the failed items from the create/update/delete dictionaries,
                    # so ContentMetadataItemTransmission objects are not synchronized for
                    # these items below.
                    self._remove_failed_items(chunked_items, items_to_create, items_to_update, items_to_delete)

                    # SAP servers throttle incoming traffic, If a request fails than the subsequent would fail too,
                    # So, no need to keep trying and failing. We should stop here and retry later.
                    skip_metadata_transmission = True

        self._create_transmissions(items_to_create)
        self._update_transmissions(items_to_update, transmission_map)
        self._delete_transmissions(items_to_delete.keys())

    def _remove_failed_items(self, failed_items, items_to_create, items_to_update, items_to_delete):
        """
        Remove content metadata items from the `items_to_create`, `items_to_update`, `items_to_delete` dicts.

        Arguments:
            failed_items (list): Failed Items to be removed.
            items_to_create (dict): dict containing the items created successfully.
            items_to_update (dict): dict containing the items updated successfully.
            items_to_delete (dict): dict containing the items deleted successfully.
        """
        for item in failed_items:
            content_metadata_id = item['courseID']
            items_to_create.pop(content_metadata_id, None)
            items_to_update.pop(content_metadata_id, None)
            items_to_delete.pop(content_metadata_id, None)

    def _prepare_items_for_transmission(self, channel_metadata_items):
        return {
            'ocnCourses': channel_metadata_items
        }

    def _prepare_items_for_delete(self, items_to_delete):
        """
        Set status to INACTIVE for items that should be deleted.
        """
        for item in items_to_delete.values():
            item['status'] = 'INACTIVE'
