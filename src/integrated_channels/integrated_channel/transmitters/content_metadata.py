"""
Generic content metadata transmitter for integrated channels.
"""

import functools
import json
import logging
from itertools import islice

import requests

from django.apps import apps
from django.conf import settings

from enterprise.utils import localized_utcnow, truncate_string
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from integrated_channels.utils import chunks, encode_binary_data_for_logging, generate_formatted_log

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
            action_name='update',
        )
        self._transmit_delete = functools.partial(
            self._transmit_action,
            client_method=self.client.delete_content_metadata,
            action_name='delete',
        )

    def _log_info(self, msg, course_or_course_run_key=None):
        LOGGER.info(
            generate_formatted_log(
                channel_name=self.enterprise_configuration.channel_code(),
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                course_or_course_run_key=course_or_course_run_key,
                plugin_configuration_id=self.enterprise_configuration.id,
                message=msg
            )
        )

    def _log_error(self, msg, course_or_course_run_key=None):
        LOGGER.error(
            generate_formatted_log(
                channel_name=self.enterprise_configuration.channel_code(),
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                course_or_course_run_key=course_or_course_run_key,
                plugin_configuration_id=self.enterprise_configuration.id,
                message=msg
            )
        )

    def _log_info_for_each_item_map(self, item_map, msg):
        for content_id, transmission in item_map.items():
            self._log_info(
                f'integrated_channel_content_transmission_id={transmission.id}, '
                f'{msg}',
                course_or_course_run_key=content_id
            )

    def transmit(self, create_payload, update_payload, delete_payload):
        """
        Transmit content metadata items to the integrated channel. Save or update content metadata records according to
        the type of transmission.
        """
        delete_payload_results = self._transmit_delete(delete_payload)

        create_payload_results = self._transmit_create(create_payload)

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

    def _filter_api_response(self, response, content_id):  # pylint: disable=unused-argument
        """
        Filter the response from the integrated channel API client.
        This can be overridden by subclasses to parse the response
        expected by the integrated channel.
        """
        return response

    def _transmit_action(self, content_metadata_item_map, client_method, action_name):  # pylint: disable=too-many-statements
        """
        Do the work of calling the appropriate client method, saving the results, and updating
        the appropriate timestamps
        """
        results = []
        chunk_items = chunks(content_metadata_item_map, self.enterprise_configuration.transmission_chunk_size)
        transmission_limit = settings.INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT.get(
            self.enterprise_configuration.channel_code()
        )

        # If we're deleting, fetch all orphaned, unresolved content transmissions
        is_delete_action = action_name == 'delete'
        successfully_removed_content_keys = []

        for chunk in islice(chunk_items, transmission_limit):
            json_payloads = [item.channel_metadata for item in list(chunk.values())]
            serialized_chunk = self._serialize_items(json_payloads)
            if self.enterprise_configuration.dry_run_mode_enabled:
                enterprise_customer_uuid = self.enterprise_configuration.enterprise_customer.uuid
                channel_code = self.enterprise_configuration.channel_code()
                for key, item in chunk.items():
                    payload = item.channel_metadata
                    serialized_payload = self._serialize_items([payload])
                    encoded_serialized_payload = encode_binary_data_for_logging(serialized_payload)
                    LOGGER.info(generate_formatted_log(
                        channel_code,
                        enterprise_customer_uuid,
                        None,
                        key,
                        f'dry-run mode content metadata '
                        f'skipping "{action_name}" action for content metadata transmission '
                        f'integrated_channel_serialized_payload_base64={encoded_serialized_payload}'
                    ))
                continue

            response_status_code = None
            response_body = None
            try:
                response_status_code, response_body = client_method(serialized_chunk)
            except ClientError as exc:
                LOGGER.exception(exc)
                response_status_code = exc.status_code
                response_body = str(exc)
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{response_body}] and status code [{response_status_code}]"
                )
            except requests.exceptions.RequestException as exc:
                LOGGER.exception(exc)
                if exc.response:
                    response_status_code = exc.response.status_code
                    response_body = exc.response.text
                else:
                    response_status_code = self.UNKNOWN_ERROR_HTTP_STATUS_CODE
                    response_body = str(exc)
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{str(exc)}] and status code [{response_status_code}]"
                )
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(exc)
                response_status_code = self.UNKNOWN_ERROR_HTTP_STATUS_CODE
                response_body = str(exc)
                self._log_error(
                    f"Failed to {action_name} [{len(chunk)}] content metadata items for integrated channel "
                    f"[{self.enterprise_configuration.enterprise_customer.name}] "
                    f"[{self.enterprise_configuration.channel_code()}]. "
                    f"Task failed with message [{response_body}]"
                )
            finally:
                action_happened_at = localized_utcnow()
                for content_id, transmission in chunk.items():
                    transmission.api_response_status_code = response_status_code
                    was_successful = response_status_code < 300
                    api_content_response = response_body
                    if was_successful:
                        api_content_response = self._filter_api_response(api_content_response, content_id)
                    (api_content_response, was_truncated) = truncate_string(api_content_response)
                    if was_truncated:
                        self._log_info(
                            f'integrated_channel_content_transmission_id={transmission.id}, '
                            f'api response truncated',
                            course_or_course_run_key=content_id
                        )
                    if transmission.api_record:
                        transmission.api_record.body = api_content_response
                        transmission.api_record.status_code = response_status_code
                        transmission.api_record.save()
                    else:
                        ApiResponseRecord = apps.get_model(
                            'integrated_channel',
                            'ApiResponseRecord'
                        )
                        transmission.api_record = ApiResponseRecord.objects.create(
                            body=api_content_response, status_code=response_status_code
                        )
                    if action_name == 'create':
                        transmission.remote_created_at = action_happened_at
                    elif action_name == 'update':
                        transmission.remote_updated_at = action_happened_at
                    elif is_delete_action:
                        transmission.remote_deleted_at = action_happened_at
                        if was_successful:
                            successfully_removed_content_keys.append(transmission.content_id)
                    if was_successful:
                        transmission.remove_marked_for()
                        transmission.remote_errored_at = None
                    else:
                        transmission.remote_errored_at = action_happened_at
                    transmission.save()
                    self.enterprise_configuration.update_content_synced_at(action_happened_at, was_successful)
                    results.append(transmission)

        if is_delete_action and successfully_removed_content_keys:
            # Mark any successfully deleted, orphaned content transmissions as resolved
            OrphanedContentTransmissions = apps.get_model(
                'integrated_channel',
                'OrphanedContentTransmissions'
            )
            orphaned_items = OrphanedContentTransmissions.objects.filter(
                integrated_channel_code=self.enterprise_configuration.channel_code(),
                plugin_configuration_id=self.enterprise_configuration.id,
                resolved=False,
            )
            orphaned_items.filter(content_id__in=successfully_removed_content_keys).update(resolved=True)

        return results
