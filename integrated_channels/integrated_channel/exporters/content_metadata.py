# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving content metadata.

Module contains resources for integrated channels to retrieve all the
metadata for content contained in the catalogs associated with a particular
enterprise customer.
"""

import json
from collections import OrderedDict
from logging import getLogger

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

        catalogs_to_transmit = []
        catalogs_last_modified = {}
        for enterprise_customer_catalog in enterprise_customer_catalogs:
            enterprise_catalog = self.enterprise_catalog_api.get_enterprise_catalog(enterprise_customer_catalog.uuid)
            if not enterprise_catalog.get('content_last_modified'):
                if enterprise_catalog.get('catalog_modified'):
                    catalog_last_modified = enterprise_catalog.get('catalog_modified')
                else:
                    catalog_last_modified = None
            elif not enterprise_catalog.get('catalog_modified'):
                catalog_last_modified = enterprise_catalog.get('content_last_modified')
            else:
                catalog_last_modified = max(
                    enterprise_catalog.get('content_last_modified'),
                    enterprise_catalog.get('catalog_modified')
                )
            last_successful_transmission = self._get_most_recent_catalog_update_time()
            if (not last_successful_transmission) or (
                catalog_last_modified and last_successful_transmission < dateparse.parse_datetime(catalog_last_modified)
            ):
                catalogs_last_modified[enterprise_catalog.get('uuid')] = catalog_last_modified
                catalogs_to_transmit.append(enterprise_catalog)

        if catalogs_to_transmit:
            return self._get_enterprise_catalog_metadata(catalogs_to_transmit, catalogs_last_modified)
        return OrderedDict([])

    def _get_enterprise_catalog_metadata(self, enterprise_catalogs, catalogs_last_modified=None):
        """
        Retrieve and transformed content metadata as a dictionary.
        """
        content_metadata_export = {}
        content_metadata_items, content_catalog_last_modified = self.enterprise_catalog_api.get_content_metadata(
            enterprise_catalogs,
            catalogs_last_modified
        )
        LOGGER.info(
            'Getting metadata for Enterprise [%s], Catalogs [%s] from Enterprise Catalog Service. Results: [%s]',
            self.enterprise_customer.name,
            self.enterprise_configuration.customer_catalogs_to_transmit,
            json.dumps(content_metadata_items)
        )
        for item in content_metadata_items:
            transformed = self._transform_item(item)
            LOGGER.debug(
                'Exporting content metadata item with plugin configuration [%s]: [%s]',
                self.enterprise_configuration,
                json.dumps(transformed, indent=4),
            )
            content_metadata_item_export = ContentMetadataItemExport(
                item, transformed, content_catalog_last_modified.get(get_content_metadata_item_id(item))
            )
            content_metadata_export[content_metadata_item_export.content_id] = content_metadata_item_export
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
                transformed_value = transformer(content_metadata_item)  # pylint: disable=not-callable
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

    def _get_most_recent_catalog_update_time(self):
        """
        Retrieve the last modified time of the catalog belonging to the most recent ContentMetadataItemTransmission for
        an enterprise customer.
        """
        # pylint: disable=invalid-name
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        past_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            integrated_channel_code=self.enterprise_configuration.channel_code(),
            catalog_last_changed__isnull=False,
        ).values('catalog_last_changed').order_by('-modified')
        if past_transmissions:
            return past_transmissions[0]['catalog_last_changed']
        return None


class ContentMetadataItemExport:
    """
    Object representation of a content metadata item export.
    """

    def __init__(self, content_metadata_item, channel_content_metadata_item, catalog_last_modified=None):
        self.content_id = get_content_metadata_item_id(content_metadata_item)
        self.metadata = content_metadata_item
        self.channel_metadata = channel_content_metadata_item
        self.catalog_last_changed = catalog_last_modified
