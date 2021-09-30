# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving content metadata.

Module contains resources for integrated channels to retrieve all the
metadata for content contained in the catalogs associated with a particular
enterprise customer.
"""

import json
from collections import OrderedDict
from datetime import datetime
from logging import getLogger

import pytz

from django.apps import apps
from django.utils import dateparse

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.exporters import Exporter

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

    def export(self, **kwargs):
        """
        Export transformed content metadata if there has been an update to the consumer's catalogs
        """
        enterprise_customer_catalogs = self.enterprise_configuration.customer_catalogs_to_transmit or \
            self.enterprise_customer.enterprise_customer_catalogs.all()

        content_metadata_export = {}
        force_retrieve_all_catalogs = kwargs.get('force_retrieve_all_catalogs', False)

        for enterprise_customer_catalog in enterprise_customer_catalogs:
            need_catalog_update = False
            if not force_retrieve_all_catalogs:
                # Retrieve the time at which the catalog and it's content were last updated
                content_last_modified, catalog_modified = self._get_enterprise_catalog_last_changed(
                    enterprise_customer_catalog
                )
                # Retrieve whatever modification happened more recently
                catalog_last_modified = max(
                    content_last_modified,
                    catalog_modified
                )
                last_successful_transmission = self._get_most_recent_catalog_update_time()
                # If the last successful transmission was since the last time the catalog was updated, there's no need
                # for an update
                need_catalog_update = (
                    not last_successful_transmission or (last_successful_transmission < catalog_last_modified)
                )

            if force_retrieve_all_catalogs or need_catalog_update:
                content_metadata_items = self.enterprise_catalog_api.get_content_metadata(
                    self.enterprise_customer,
                    [enterprise_customer_catalog]
                )
                LOGGER.info(
                    f'Content metadata exporter found {len(content_metadata_items)} items that need updates'
                    f' under catalog {enterprise_customer_catalog.uuid}'
                )
                for item in content_metadata_items:
                    transformed = self._transform_item(item)
                    LOGGER.debug(
                        'Exporting content metadata item with plugin configuration [%s]: [%s]',
                        self.enterprise_configuration,
                        json.dumps(transformed, indent=4),
                    )

                    # There are some scenarios where `content_last_modified` isn't present in the fetched content
                    content_last_modified = item.get('content_last_modified')
                    if content_last_modified:
                        content_last_modified = item.pop('content_last_modified')
                    else:
                        LOGGER.warning(
                            "content_last_modified field not found for {} - {} under catalog: {}".format(
                                item.get('content_type'),
                                item.get('key'),
                                enterprise_customer_catalog.uuid,
                            )
                        )

                    content_metadata_item_export = ContentMetadataItemExport(
                        content_metadata_item=item,
                        channel_content_metadata_item=transformed,
                        content_last_changed=content_last_modified,
                        enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid
                    )
                    content_metadata_export[content_metadata_item_export.content_id] = content_metadata_item_export
            else:
                ContentMetadataItemTransmission = apps.get_model(
                    'integrated_channel',
                    'ContentMetadataItemTransmission'
                )
                past_catalog_transmission_queryset = ContentMetadataItemTransmission.objects.filter(
                    enterprise_customer=self.enterprise_configuration.enterprise_customer,
                    integrated_channel_code=self.enterprise_configuration.channel_code(),
                    enterprise_customer_catalog_uuid=enterprise_customer_catalog.uuid
                )
                LOGGER.info(
                    f'Content metadata exporter found {len(past_catalog_transmission_queryset)} past content items that'
                    f' need no update under catalog {enterprise_customer_catalog.uuid}'
                )
                for past_transmission in past_catalog_transmission_queryset:
                    # In order to determine if something doesn't need updates vs needing to be deleted, the transmitter
                    # expects a value to be present for every content item within the customer's catalogs. By adding the
                    # past transmission, the transmitter will recognize that no update is needed.
                    content_metadata_export[past_transmission.content_id] = past_transmission

        return OrderedDict(sorted(content_metadata_export.items()))

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
                    LOGGER.exception(
                        'Failed to transform content metadata item field [%s] for [%s]: [%s]',
                        edx_data_schema_key,
                        self.enterprise_customer.name,
                        content_metadata_item,
                    )
                    continue

            if transformed_value is None and self.SKIP_KEY_IF_NONE:
                continue
            transformed_item[integrated_channel_schema_key] = transformed_value

        return transformed_item

    def _get_enterprise_catalog_last_changed(self, enterprise_catalog):
        """
        Retrieves catalog metadata, specifically selecting for `content_last_modified` and `catalog_modified`.
        """
        enterprise_catalog_data = self.enterprise_catalog_api.get_enterprise_catalog(
            enterprise_catalog.uuid
        )
        content_last_modified = enterprise_catalog_data.get('content_last_modified')
        content_last_modified = dateparse.parse_datetime(
            content_last_modified
        ) if content_last_modified else datetime.min.replace(tzinfo=pytz.UTC)

        catalog_modified = enterprise_catalog_data.get('catalog_modified')
        catalog_modified = dateparse.parse_datetime(
            catalog_modified
        ) if catalog_modified else datetime.min.replace(tzinfo=pytz.UTC)
        return content_last_modified, catalog_modified

    def _get_most_recent_catalog_update_time(self):
        """
        Retrieve the last modified time of the catalog belonging to the most recent ContentMetadataItemTransmission for
        an enterprise customer.
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        past_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code(),
            content_last_changed__isnull=False,
        ).values('content_last_changed').order_by('-content_last_changed')
        if past_transmissions:
            return past_transmissions[0]['content_last_changed']
        return None

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
                content_id__in=content_ids
            )
            LOGGER.info(
                f'Found {len(transmission_items)} past content transmissions that need to be updated with their'
                f' respective catalog (catalog: {enterprise_customer_catalog.uuid}) UUIDs'
            )
            for item in transmission_items:
                item.enterprise_customer_catalog_uuid = enterprise_customer_catalog.uuid
                item.save()


class ContentMetadataItemExport:
    """
    Object representation of a content metadata item export.
    """

    def __init__(
        self,
        content_metadata_item,
        channel_content_metadata_item,
        enterprise_customer_catalog_uuid,
        content_last_changed=None
    ):
        self.content_id = get_content_metadata_item_id(content_metadata_item)
        self.channel_metadata = channel_content_metadata_item
        self.content_last_changed = content_last_changed
        self.enterprise_customer_catalog_uuid = enterprise_customer_catalog_uuid
