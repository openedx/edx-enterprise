# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving content metadata.

Module contains resources for integrated channels to retrieve all the
metadata for content contained in the catalogs associated with a particular
enterprise customer.
"""

from __future__ import absolute_import, unicode_literals

import json
from collections import OrderedDict
from logging import getLogger

from enterprise.api_client.enterprise import EnterpriseApiClient
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

    def __init__(self, user, enterprise_configuration):
        """
        Initialize the exporter.
        """
        super(ContentMetadataExporter, self).__init__(user, enterprise_configuration)
        self.enterprise_api = EnterpriseApiClient(self.user)

    def export(self):
        """
        Return the exported and transformed content metadata as a dictionary.
        """
        content_metadata_export = {}
        content_metadata_items = self.enterprise_api.get_content_metadata(self.enterprise_customer)
        LOGGER.info('Retrieved content metadata for enterprise [%s]', self.enterprise_customer.name)
        for item in content_metadata_items:
            transformed = self._transform_item(item)
            LOGGER.info(
                'Exporting content metadata item with plugin configuration [%s]: [%s]',
                self.enterprise_configuration,
                json.dumps(transformed, indent=4),
            )
            content_metadata_item_export = ContentMetadataItemExport(item, transformed)
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
                transformed_item[integrated_channel_schema_key] = transformer(content_metadata_item)
            else:
                # The concrete subclass does not define an override for the given field,
                # so just use the data key to index the content metadata item dictionary.
                try:
                    transformed_item[integrated_channel_schema_key] = content_metadata_item[edx_data_schema_key]
                except KeyError:
                    # There may be a problem with the DATA_TRANSFORM_MAPPING on
                    # the concrete subclass or the concrete subclass does not implement
                    # the appropriate field tranformer function.
                    LOGGER.exception(
                        'Failed to transform content metadata item field [%s] for [%s]: [%s]',
                        edx_data_schema_key,
                        self.enterprise_customer.name,
                        content_metadata_item,
                    )

        return transformed_item


class ContentMetadataItemExport(object):
    """
    Object representation of a content metadata item export.
    """

    def __init__(self, content_metadata_item, channel_content_metadata_item):
        self.content_id = get_content_metadata_item_id(content_metadata_item)
        self.metadata = content_metadata_item
        self.channel_metadata = channel_content_metadata_item
