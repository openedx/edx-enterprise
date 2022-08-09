"""
Tests for the base content metadata exporter.
"""

import datetime
import logging
import unittest
from collections import OrderedDict
from unittest import mock

from pytest import mark
from testfixtures import LogCapture

from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import (
    FAKE_COURSE_RUN,
    get_fake_catalog,
    get_fake_catalog_diff_create,
    get_fake_content_metadata,
)
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``ContentMetadataExporter`` class.
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        self.fake_catalog = get_fake_catalog()
        self.fake_catalog_modified_at = max(
            self.fake_catalog['content_last_modified'], self.fake_catalog['catalog_modified']
        )
        self.fake_catalogs_last_modified = {
            get_content_metadata_item_id(
                content_metadata
            ): self.fake_catalog_modified_at for content_metadata in get_fake_content_metadata()
        }
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_create_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not delete_payload

        assert mock_get_content_metadata.get(FAKE_COURSE_RUN['key'])

        for key in create_payload:
            assert key in ['edX+DemoX', 'course-v1:edX+DemoX+Demo_Course', FAKE_UUIDS[3]]

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_delete_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a delete payload of the course data when retrieving catalog
        diffs with content to delete.
        """
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission.save()
        mock_create_items = []
        mock_delete_items = [{'content_key': FAKE_COURSE_RUN['key']}]
        mock_matched_items = []
        mock_get_catalog_diff.return_value = mock_create_items, mock_delete_items, mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        assert not create_payload
        assert not update_payload
        assert delete_payload.get(FAKE_COURSE_RUN['key']) == past_transmission
        # Sanity check
        mock_get_content_metadata.assert_not_called()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_failed_create_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a delete payload of the course data when retrieving catalog
        diffs with content to delete.
        """
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=None,
            remote_updated_at=None,
            remote_deleted_at=None,
        )
        past_transmission.save()
        mock_create_items = [{'content_key': FAKE_COURSE_RUN['key']}]
        mock_delete_items = []
        mock_matched_items = []
        mock_get_catalog_diff.return_value = mock_create_items, mock_delete_items, mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        assert create_payload.get(FAKE_COURSE_RUN['key']) == past_transmission
        assert not update_payload
        assert not delete_payload
        # Sanity check
        mock_get_content_metadata.assert_not_called()

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_update_not_needed_export(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING = {
            'contentId': 'key',
            'title': 'title',
            'description': 'description',
            'imageUrl': 'image',
            'url': 'enrollment_url',
            'language': 'content_language'
        }
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission.save()

        mock_content_metadata_response = OrderedDict()
        mock_content_metadata_response[FAKE_COURSE_RUN['key']] = FAKE_COURSE_RUN
        mock_api_client.return_value.get_content_metadata.return_value = list(mock_content_metadata_response.values())
        mock_create_items = []
        mock_delete_items = []
        mock_matched_items = [{'content_key': FAKE_COURSE_RUN['key'], 'date_updated': datetime.datetime.now()}]
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert update_payload.get(FAKE_COURSE_RUN['key']).channel_metadata.get('contentId') == FAKE_COURSE_RUN['key']
        assert not create_payload
        assert not delete_payload

        mock_api_client.return_value.get_catalog_diff.assert_called_with(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
            [FAKE_COURSE_RUN['key']]
        )

        past_transmission.content_last_changed = datetime.datetime.now()
        past_transmission.save()

        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not create_payload
        assert not delete_payload
        assert mock_api_client.return_value.get_catalog_diff.call_count == 2
        assert mock_api_client.return_value.get_content_metadata.call_count == 1

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_bad_data_transform_mapping(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` raises an exception when DATA_TRANSFORM_MAPPING is invalid.
        """
        content_id = 'course:DemoX'

        mock_api_client.return_value.get_content_metadata.return_value = get_fake_content_metadata()
        mock_create_items = [{'content_key': content_id}]
        mock_delete_items = {}
        mock_matched_items = []
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING['fake-key'] = 'fake-value'
        exporter = ContentMetadataExporter('fake-user', self.config)
        with LogCapture(level=logging.ERROR) as log_capture:
            exporter.export()
            assert 'Failed to transform content metadata item field' in log_capture.records[0].getMessage()
            assert self.enterprise_customer_catalog.enterprise_customer.name in log_capture.records[0].getMessage()

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_export_fetches_content_only_when_update_needed(self, mock_ent_catalog_api):
        """
        Test that when a ContentMetadataItemTransmission exists with a `catalog_last_changed` field that comes after the
        last modified time of content's associated catalog, we don't fetch the catalog's metadata.
        """
        # Generate a past transmission item that will indicate no updated needed
        past_content_transmission = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid
        )
        mock_ent_catalog_api.return_value.get_content_metadata.return_value = get_fake_content_metadata()
        mock_create_items = []
        mock_delete_items = {}
        mock_matched_items = [
            {'content_key': past_content_transmission.content_id, 'date_updated': '2021-07-16T15:11:10.521611Z'}
        ]
        mock_ent_catalog_api.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not create_payload
        assert not update_payload
        assert not delete_payload

        # We should make a call for the enterprise catalog, but no call for the metadata because no update needed
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_count == 0
        assert mock_ent_catalog_api.return_value.get_catalog_diff.call_count == 1
