# -*- coding: utf-8 -*-
"""
Class for transmitting content metadata to SuccessFactors.
"""

import logging
from itertools import islice

from django.conf import settings

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.utils import chunks, generate_formatted_log

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

    def transmit(self, create_payload, update_payload, delete_payload, content_updated_mapping, **kwargs):
        """
        Transmit content metadata items to the integrated channel.
        """
        # Since delete_payload is a mapping between content key and past transmission record, we need to create a
        # mapping between content key and channel_metadata. Then we can prepare the channel metadata for deletion
        items_to_delete = {key: item.channel_metadata for key, item in delete_payload.items()}
        self._prepare_items_for_delete(items_to_delete)

        prepared_items = {}
        prepared_items.update(create_payload)

        # Do the same work to the update payload as was done to the delete payload above
        items_to_update = {key: item.channel_metadata for key, item in update_payload.items()}
        prepared_items.update(items_to_update)
        prepared_items.update(items_to_delete)

        chunk_items = chunks(prepared_items, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            chunked_items = list(chunk.values())
            try:
                self.client.update_content_metadata(self._serialize_items(chunked_items))
            except ClientError as exc:
                LOGGER.error(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'Failed to update [{len(chunked_items)}] content metadata items for '
                        f'integrated channel {self.enterprise_configuration.enterprise_customer.name} '
                        f'{self.enterprise_configuration.channel_code()}'
                    )
                )
                LOGGER.exception(exc)

                # Remove the failed items from the create/update/delete dictionaries,
                # so ContentMetadataItemTransmission objects are not synchronized for
                # these items below.
                self._remove_failed_items(chunked_items, create_payload, items_to_update, items_to_delete)

        # If API transmission limit is set then mark the rest of the items as not transmitted.
        # Since, chunk_items is a generator and we have already iterated through the items that need to
        # be transmitted. Rest of the items are the ones that need to marked as not transmitted.
        for chunk in chunk_items:
            chunked_items = list(chunk.values())
            self._remove_failed_items(chunked_items, create_payload, items_to_update, items_to_delete)

        self._create_transmissions(create_payload, content_updated_mapping)
        self._update_transmissions(update_payload, content_updated_mapping)
        self._delete_transmissions(list(items_to_delete.keys()))

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
