"""
Generic content metadata transmitter for integrated channels.
"""

import functools
import json
import logging
from datetime import datetime
from itertools import islice
import requests

from django.conf import settings

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from integrated_channels.utils import chunks, generate_formatted_log

LOGGER = logging.getLogger(__name__)


class ContentMetadataTransmitter(Transmitter):
    """
    Used to transmit content metadata to an integrated channel.
    """

    # a 'magic number' to designate an unknown error
    UNKNOWN_ERROR_HTTP_STATUS_CODE = 555


    def __init__(self, enterprise_configuration, client=IntegratedChannelApiClient):
        """
        By default, use the abstract integrated channel API client which raises an error when used if not subclassed.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
        self._transmit_create = functools.partial(
            self._transmit_action,
            client_method=self.client.create_content_metadata,
            action_name='create',
        )
        self._transmit_update = functools.partial(
            self._transmit_action,
            client_method=self.client.update_content_metadata,
            action_name='update'
        )
        self._transmit_delete = functools.partial(
            self._transmit_action,
            client_method=self.client.delete_content_metadata,
            action_name='delete'
        )

    def _log_info(self, msg, course_or_course_run_key=None):
        LOGGER.info(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                course_or_course_run_key,
                msg
            )
        )

    def _log_error(self, msg, course_or_course_run_key=None):
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                course_or_course_run_key,
                msg
            )
        )

    def _log_info_for_each_item_map(self, item_map, msg):
        for content_id, transmission in item_map.items():
            self._log_info(
                f'integrated_channel_content_transmission_id={transmission.id}, '
                f'{msg}',
                course_or_course_run_key=content_id
            )

    def transmit(self, create_payload, update_payload, delete_payload, **kwargs):
        """
        Transmit content metadata items to the integrated channel. Save or update content metadata records according to
        the type of transmission.
        """
        self._log_info_for_each_item_map(delete_payload, 'transmitting delete')
        delete_payload_results = self._transmit_delete(delete_payload)

        self._log_info_for_each_item_map(create_payload, 'transmitting create')
        create_payload_results = self._transmit_create(create_payload)

        self._log_info_for_each_item_map(update_payload, 'transmitting update')
        update_payload_results = self._transmit_update(update_payload)
        return create_payload_results, update_payload_results, delete_payload_results

    def _prepare_items_for_transmission(self, channel_metadata_items):
        """
        Perform any necessary modifications to content metadata item
        data structure before transmission. This can be overridden by
        subclasses to add any data structure wrappers expected by the
        integrated channel.
        """
        return channel_metadata_items

    def _prepare_items_for_delete(self, channel_metadata_items):
        """
        Perform any necessary modifications to content metadata item
        data structure before delete. This can be overridden by
        subclasses to add any data structure wrappers expected by the
        integrated channel.
        """
        return channel_metadata_items

    def _serialize_items(self, channel_metadata_items):
        """
        Serialize content metadata items for a create transmission to the integrated channel.
        """
        return json.dumps(
            self._prepare_items_for_transmission(channel_metadata_items),
            sort_keys=True
        ).encode('utf-8')

    def _transmit_action(self, content_metadata_item_map, client_method, action_name):
        """
        Do the work of calling the appropriate client method, saving the results, and updating
        the appropriate timestamps
        """
        results = []
        chunk_items = chunks(content_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )
        for chunk in islice(chunk_items, transmission_limit):
            json_payloads = [item.channel_metadata for item in list(chunk.values())]
            serialized_chunk = self._serialize_items(json_payloads)
            response_status_code = None
            response_body = None
            try:
                response_status_code, response_body = client_method(serialized_chunk)
            except ClientError as exc:
                LOGGER.exception(exc)
                response_status_code = exc.status_code
                response_body = exc.message
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{exc.message}] and status code [{response_status_code}]"
                )
            except requests.exceptions.RequestException as exc:
                LOGGER.exception(exc)
                if exc.response:
                    response_status_code = exc.response.status_code
                    response_body = exc.response.text
                else:
                    response_status_code = UNKNOWN_ERROR_HTTP_STATUS_CODE
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{exc.message}] and status code [{response_status_code}]"
                )
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(exc)
                response_status_code = UNKNOWN_ERROR_HTTP_STATUS_CODE
                response_body = exc.message
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{exc.message}]"
                )
            finally:
                action_happened_at = datetime.utcnow()
                for content_id, transmission in chunk.items():
                    self._log_info(
                        f'integrated_channel_content_transmission_id={transmission.id}, '
                        f'saving {action_name} transmission',
                        course_or_course_run_key=content_id
                    )
                    transmission.api_response_status_code = response_status_code
                    transmission.api_response_body = response_body
                    if action_name == 'create':
                        transmission.remote_created_at = action_happened_at
                    elif action_name == 'update':
                        transmission.remote_updated_at = action_happened_at
                    elif action_name == 'delete':
                        transmission.remote_deleted_at = action_happened_at
                    transmission.save()
                    results.append(transmission)
        return results
