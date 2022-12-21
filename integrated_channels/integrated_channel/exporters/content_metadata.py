"""
Assist integrated channels with retrieving content metadata.

Module contains resources for integrated channels to retrieve all the
metadata for content contained in the catalogs associated with a particular
enterprise customer.
"""

import sys
from logging import getLogger

from django.apps import apps
from django.db.models import Q

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.constants import EXEC_ED_CONTENT_DESCRIPTION_TAG, EXEC_ED_COURSE_TYPE, TRANSMISSION_MARK_CREATE
from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.exporters import Exporter
from integrated_channels.utils import generate_formatted_log, truncate_item_dicts

LOGGER = getLogger(__name__)


class ContentMetadataExporter(Exporter):
    """
    Base class for content metadata exporters.
    """

    # DATA_TRANSFORM_MAPPING is used to map the content metadata field names expected by the integrated channel
    # to the edX content metadata schema. The values contained in the dict will be used as keys to access values
    # in each content metadata item dict which is being exported.
    #
    # Example:
    #     {
    #         'contentID': 'key',
    #         'courseTitle': 'title'
    #     }
    #
    #     Defines a transformation of the content metadata item to:
    #
    #     {
    #         'contentID': content_metadata_item['key'],
    #         'courseTitle': content_metadata_item['title']
    #     }
    #
    # Subclasses should override this class variable. By default, the edX content metadata schema is returned in
    # its entirety.
    #
    # In addition, subclasses can implement transform functions which receive a content metadata item for more
    # complicated field transformations. These functions can be content type-specific or generic for all content
    # types.
    #
    # Example:
    #     DATA_TRANSFORM_MAPPING = {
    #         'coursePrice': 'price'
    #     }
    #     # Content type-specific transformer
    #     def transform_course_price(self, course):
    #         return course['course_runs'][0]['seats']['verified]['price']
    #     # Generic transformer
    #     def transform_provider_id(self, course):
    #         return self.enterprise_configuration.provider_id
    #
    # TODO: Move this to the EnterpriseCustomerPluginConfiguration model as a JSONField.
    DATA_TRANSFORM_MAPPING = {}
    SKIP_KEY_IF_NONE = False

    def __init__(self, user, enterprise_configuration):
        """
        Initialize the exporter.
        """
        super().__init__(user, enterprise_configuration)
        self.enterprise_catalog_api = EnterpriseCatalogApiClient(self.user)

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

    def _log_exception(self, msg, course_or_course_run_key=None):
        LOGGER.exception(
            generate_formatted_log(
                channel_name=self.enterprise_configuration.channel_code(),
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                course_or_course_run_key=course_or_course_run_key,
                plugin_configuration_id=self.enterprise_configuration.id,
                message=msg
            )
        )

    def _get_catalog_content_keys(self, enterprise_customer_catalog):
        """
        Retrieve all non-deleted content transmissions under a given customer's catalog
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        past_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code(),
            enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid,
            plugin_configuration_id=self.enterprise_configuration.id,
            remote_deleted_at__isnull=True,
            remote_created_at__isnull=False,
        ).values('content_id')
        if not past_transmissions:
            return []
        return [key.get('content_id') for key in past_transmissions]

    def _check_matched_content_updated_at(
        self,
        enterprise_customer_catalog,
        matched_items,
        force_retrieve_all_catalogs
    ):
        """
        Take a list of content keys and their respective last updated time and build a mapping between content keys and
        past content metadata transmission record when the last updated time comes after the last updated time of the
        record.

        Args:
            enterprise_customer_catalog (EnterpriseCustomerCatalog): The enterprise catalog object

            matched_items (list): A list of dicts containing content keys and the last datetime that the respective
                content was updated

            force_retrieve_all_catalogs (Bool): If set to True, all content under the catalog will be retrieved,
                regardless of the last updated at time
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        items_to_update = {}
        for matched_item in matched_items:
            content_id = matched_item.get('content_key')
            content_last_changed = matched_item.get('date_updated')
            incomplete_transmission = ContentMetadataItemTransmission.incomplete_update_transmissions(
                enterprise_customer=self.enterprise_configuration.enterprise_customer,
                plugin_configuration_id=self.enterprise_configuration.id,
                integrated_channel_code=self.enterprise_configuration.channel_code(),
                content_id=content_id,
            ).first()
            if incomplete_transmission:
                self._log_info(
                    'Found an unsent content update record while creating record. '
                    'Including record.',
                    course_or_course_run_key=content_id
                )
                incomplete_transmission.mark_for_update()
                items_to_update[content_id] = incomplete_transmission
            else:
                content_query = Q(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    integrated_channel_code=self.enterprise_configuration.channel_code(),
                    enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid,
                    plugin_configuration_id=self.enterprise_configuration.id,
                    content_id=content_id,
                    remote_deleted_at__isnull=True,
                    remote_created_at__isnull=False,
                )
                # If not force_retrieve_all_catalogs, filter content records where `content last changed` is less than
                # the matched item's `date_updated`, otherwise select the row regardless of what the updated at time is.
                if not force_retrieve_all_catalogs:
                    last_changed_query = Q(content_last_changed__lt=content_last_changed)
                    last_changed_query.add(Q(content_last_changed__isnull=True), Q.OR)
                    get_marked_for = Q(marked_for='update')
                    get_marked_for.add(last_changed_query, Q.OR)
                    content_query.add(get_marked_for, Q.AND)
                items_to_update_query = ContentMetadataItemTransmission.objects.filter(content_query)
                item = items_to_update_query.first()
                if item:
                    item.mark_for_update()
                    items_to_update[content_id] = item
        return items_to_update

    def _check_matched_content_to_create(
        self,
        enterprise_customer_catalog,
        matched_items
    ):
        """
        Take a list of content keys and create ContentMetadataItemTransmission records. When existed soft-deleted
        records exist, resurrect them. When created but not-yet-transmitted records exist, include them.

        Args:
            enterprise_customer_catalog (EnterpriseCustomerCatalog): The enterprise catalog object

            matched_items (list): A list of dicts containing content keys and the last datetime that the respective
                content was updated

            force_retrieve_all_catalogs (Bool): If set to True, all content under the catalog will be retrieved,
                regardless of the last updated at time
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        items_to_create = {}
        for matched_item in matched_items:
            content_id = matched_item.get('content_key')
            content_last_changed = matched_item.get('date_updated')
            past_deleted_transmission = ContentMetadataItemTransmission.deleted_transmissions(
                enterprise_customer=self.enterprise_configuration.enterprise_customer,
                plugin_configuration_id=self.enterprise_configuration.id,
                integrated_channel_code=self.enterprise_configuration.channel_code(),
                content_id=content_id,
            ).first()
            if past_deleted_transmission:
                self._log_info(
                    'Found previously deleted content record while creating record. '
                    'Marking record as active.',
                    course_or_course_run_key=content_id
                )
                past_deleted_transmission.prepare_to_recreate(content_last_changed, enterprise_customer_catalog.uuid)
                items_to_create[content_id] = past_deleted_transmission
            else:
                incomplete_transmission = ContentMetadataItemTransmission.incomplete_create_transmissions(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    plugin_configuration_id=self.enterprise_configuration.id,
                    integrated_channel_code=self.enterprise_configuration.channel_code(),
                    content_id=content_id,
                ).first()
                if incomplete_transmission:
                    self._log_info(
                        'Found an unsent content create record while creating record. '
                        'Including record.',
                        course_or_course_run_key=content_id
                    )
                    incomplete_transmission.mark_for_create()
                    items_to_create[content_id] = incomplete_transmission
                else:
                    new_transmission = ContentMetadataItemTransmission(
                        enterprise_customer=self.enterprise_configuration.enterprise_customer,
                        integrated_channel_code=self.enterprise_configuration.channel_code(),
                        content_id=content_id,
                        channel_metadata=None,
                        content_last_changed=content_last_changed,
                        enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid,
                        plugin_configuration_id=self.enterprise_configuration.id,
                        marked_for=TRANSMISSION_MARK_CREATE
                    )
                    new_transmission.save()
                    items_to_create[content_id] = new_transmission
        return items_to_create

    def _get_catalog_diff(
        self,
        enterprise_catalog,
        content_keys,
        force_retrieve_all_catalogs,
        max_item_count
    ):
        """
        From the enterprise catalog API, request a catalog diff based off of a list of content keys. Using the diff,
        retrieve past content metadata transmission records for update and delete payloads.
        """
        items_to_create, items_to_delete, matched_items = self.enterprise_catalog_api.get_catalog_diff(
            enterprise_catalog,
            content_keys
        )

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        # Fetch all existing, non-deleted transmission audit content keys for the customer/configuration
        existing_content_keys = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code(),
            plugin_configuration_id=self.enterprise_configuration.id,
            remote_deleted_at__isnull=True,
            remote_created_at__isnull=False,
        ).values_list("content_id", flat=True)
        unique_new_items_to_create = []

        # We need to remove any potential create transmissions if the content already exists on the customer's instance
        # under a different catalog
        for item in items_to_create:
            if item.get('content_key') not in existing_content_keys:
                unique_new_items_to_create.append(item)
            else:
                self._log_info(
                    'Found an previous content record in another catalog while creating. '
                    'Skipping record.',
                    course_or_course_run_key=item.get('content_key')
                )

        content_to_create = self._check_matched_content_to_create(
            enterprise_catalog,
            unique_new_items_to_create
        )
        content_to_update = self._check_matched_content_updated_at(
            enterprise_catalog,
            matched_items,
            force_retrieve_all_catalogs
        )
        content_to_delete = self._check_matched_content_to_delete(
            enterprise_catalog,
            items_to_delete
        )

        truncated_create, truncated_update, truncated_delete = truncate_item_dicts(
            content_to_create,
            content_to_update,
            content_to_delete,
            max_item_count
        )

        return truncated_create, truncated_update, truncated_delete

    def _check_matched_content_to_delete(self, enterprise_customer_catalog, items):
        """
        Retrieve all past content metadata transmission records that have a `content_id` contained within a provided
        list.
        renamed from _retrieve_past_transmission_content
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        items_to_delete = {}
        for item in items:
            content_id = item.get('content_key')

            incomplete_transmission = ContentMetadataItemTransmission.incomplete_delete_transmissions(
                enterprise_customer=self.enterprise_configuration.enterprise_customer,
                plugin_configuration_id=self.enterprise_configuration.id,
                integrated_channel_code=self.enterprise_configuration.channel_code(),
                content_id=content_id,
            ).first()

            if incomplete_transmission:
                self._log_info(
                    'Found an unsent content delete record while deleting record. '
                    'Including record.',
                    course_or_course_run_key=content_id
                )
                incomplete_transmission.mark_for_delete()
                items_to_delete[content_id] = incomplete_transmission
            else:
                past_content = ContentMetadataItemTransmission.objects.filter(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    integrated_channel_code=self.enterprise_configuration.channel_code(),
                    enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid,
                    plugin_configuration_id=self.enterprise_configuration.id,
                    content_id=content_id
                ).first()
                if past_content:
                    past_content.mark_for_delete()
                    items_to_delete[content_id] = past_content
                else:
                    self._log_info(
                        'Could not find a content record while deleting record. '
                        'Skipping record.',
                        course_or_course_run_key=content_id
                    )
        return items_to_delete

    def export(self, **kwargs):
        """
        Export transformed content metadata if there has been an update to the consumer's catalogs
        """
        enterprise_customer_catalogs = self.enterprise_configuration.customer_catalogs_to_transmit or \
            self.enterprise_customer.enterprise_customer_catalogs.all()

        # a maximum number of changes/payloads to export at once
        # default to something huge to simplifly logic, the max system int size
        max_payload_count = kwargs.get('max_payload_count', sys.maxsize)

        self._log_info(
            f'Beginning export for customer: {self.enterprise_customer.uuid}, with '
            f'max_payload_count of {max_payload_count}, and catalogs: '
            f'{enterprise_customer_catalogs}'
        )

        create_payload = {}
        update_payload = {}
        delete_payload = {}
        for enterprise_customer_catalog in enterprise_customer_catalogs:

            # if we're already at the max in a multi-catalog situation, break out
            if len(create_payload) + len(update_payload) + len(delete_payload) >= max_payload_count:
                self._log_info(f'Reached max_payload_count of {max_payload_count} breaking.')
                break

            content_keys = self._get_catalog_content_keys(enterprise_customer_catalog)

            self._log_info(
                f'Retrieved {len(content_keys)} content keys for past transmissions to customer: '
                f'{self.enterprise_customer.uuid} under catalog: {enterprise_customer_catalog.uuid}.'
            )

            # From the saved content records, use the enterprise catalog API to determine what needs sending
            items_to_create, items_to_update, items_to_delete = self._get_catalog_diff(
                enterprise_customer_catalog,
                content_keys,
                kwargs.get('force_retrieve_all_catalogs', False),
                max_payload_count
            )

            self._log_info(f'diff items_to_create: {items_to_create}')
            self._log_info(f'diff items_to_update: {items_to_update}')
            self._log_info(f'diff items_to_delete: {items_to_delete}')

            # We only need to fetch content metadata if there are items to update or create
            if items_to_create or items_to_update:
                items_create_keys = list(items_to_create.keys())
                items_update_keys = list(items_to_update.keys())
                content_keys_filter = items_create_keys + items_update_keys
                content_metadata_items = self.enterprise_catalog_api.get_content_metadata(
                    self.enterprise_customer,
                    [enterprise_customer_catalog],
                    content_keys_filter,
                )
                for item in content_metadata_items:
                    key = get_content_metadata_item_id(item)

                    # Ensure executive education content is properly tagged before transforming the content to
                    # the channel specific, expected form
                    item = self._transform_exec_ed_content(item)

                    # transform the content metadata into the channel specific format
                    transformed_item = self._transform_item(item)
                    if key in items_create_keys:
                        existing_record = items_to_create.get(key)
                        existing_record.channel_metadata = transformed_item
                        existing_record.content_title = item.get('title')
                        existing_record.content_last_changed = item.get('content_last_modified')
                        # Sanity check
                        existing_record.enterprise_customer_catalog_uuid = enterprise_customer_catalog.uuid
                        existing_record.save()
                        create_payload[key] = existing_record
                    elif key in items_update_keys:
                        existing_record = items_to_update.get(key)
                        existing_record.content_title = item.get('title')
                        # Sanity check
                        existing_record.enterprise_customer_catalog_uuid = enterprise_customer_catalog.uuid
                        existing_record.save()
                        # Intentionally setting the channel_metadata and content_last_changed
                        # fields post-save to clarify what data has been transmitted
                        # and so that untransmitted courses will get picked up again in subsequent runs
                        existing_record.content_last_changed = item.get('content_last_modified')
                        existing_record.channel_metadata = transformed_item
                        update_payload[key] = existing_record

            for key, item in items_to_delete.items():
                delete_payload[key] = item

        self._log_info(
            f'Exporter finished for customer: {self.enterprise_customer.uuid} with payloads- create_payload: '
            f'{create_payload}, update_payload: {update_payload}, delete_payload: {delete_payload}'
        )

        # collections of ContentMetadataItemTransmission objects
        return create_payload, update_payload, delete_payload

    def _transform_exec_ed_content(self, content):
        """
        Transform only executive education course type content to add executive education identifying tags to both the
        title and description of the content
        """
        if content.get('course_type') == EXEC_ED_COURSE_TYPE:
            if title := content.get('title'):
                content['title'] = "ExecEd: " + title
            if description := content.get('full_description'):
                content['full_description'] = EXEC_ED_CONTENT_DESCRIPTION_TAG + description
        return content

    def _transform_item(self, content_metadata_item):
        """
        Transform the provided content metadata item to the schema expected by the integrated channel.
        """
        content_metadata_type = content_metadata_item['content_type']
        transformed_item = {}
        for integrated_channel_schema_key, edx_data_schema_key in self.DATA_TRANSFORM_MAPPING.items():
            # Look for transformer functions defined on subclasses.
            # Favor content type-specific functions.
            transformer = (
                getattr(
                    self,
                    'transform_{content_type}_{edx_data_schema_key}'.format(
                        content_type=content_metadata_type,
                        edx_data_schema_key=edx_data_schema_key
                    ),
                    None
                )
                or
                getattr(
                    self,
                    'transform_{edx_data_schema_key}'.format(
                        edx_data_schema_key=edx_data_schema_key
                    ),
                    None
                )
            )
            if transformer:
                transformed_value = transformer(content_metadata_item)
            else:
                # The concrete subclass does not define an override for the given field,
                # so just use the data key to index the content metadata item dictionary.
                try:
                    transformed_value = content_metadata_item[edx_data_schema_key]
                except KeyError:
                    # There may be a problem with the DATA_TRANSFORM_MAPPING on
                    # the concrete subclass or the concrete subclass does not implement
                    # the appropriate field transformer function.
                    self._log_exception(
                        f'Failed to transform content metadata item field {edx_data_schema_key} '
                        f'for {self.enterprise_customer.name}: {content_metadata_item}'
                    )
                    continue

            if transformed_value is None and self.SKIP_KEY_IF_NONE:
                continue
            transformed_item[integrated_channel_schema_key] = transformed_value

        return transformed_item

    def update_content_transmissions_catalog_uuids(self):
        """
        Retrieve all content under the enterprise customer's catalog(s) and update all past transmission audits to have
        it's associated catalog uuid.
        """
        enterprise_customer_catalogs = self.enterprise_configuration.customer_catalogs_to_transmit or \
            self.enterprise_customer.enterprise_customer_catalogs.all()

        for enterprise_customer_catalog in enterprise_customer_catalogs:
            content_metadata_items = self.enterprise_catalog_api.get_content_metadata(
                self.enterprise_customer,
                [enterprise_customer_catalog]
            )
            content_ids = [get_content_metadata_item_id(item) for item in content_metadata_items]
            ContentMetadataItemTransmission = apps.get_model(
                'integrated_channel',
                'ContentMetadataItemTransmission'
            )
            transmission_items = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_configuration.enterprise_customer,
                integrated_channel_code=self.enterprise_configuration.channel_code(),
                plugin_configuration_id=self.enterprise_configuration.id,
                content_id__in=content_ids
            )
            self._log_info(
                f'Found {len(transmission_items)} past content transmissions that need to be updated with their '
                f'respective catalog (catalog: {enterprise_customer_catalog.uuid}) UUIDs'
            )
            for item in transmission_items:
                item.enterprise_customer_catalog_uuid = enterprise_customer_catalog.uuid
                item.save()
