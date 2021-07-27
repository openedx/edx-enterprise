# -*- coding: utf-8 -*-
"""
Tests for the base content metadata exporter.
"""

import logging
import unittest

import mock
from pytest import mark
from testfixtures import LogCapture

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import get_fake_catalog, get_fake_content_metadata
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
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_enterprise_catalog')
    def test_content_exporter_export(self, mock_get_enterprise_catalog, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata(), {}
        mock_get_enterprise_catalog.return_value = get_fake_catalog()
        exporter = ContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_export_with_catalogs_to_transmit(self, mock_ent_catalog_api):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_ent_catalog_api.return_value.get_content_metadata.return_value = get_fake_content_metadata(), {}
        mock_ent_catalog_api.return_value.get_enterprise_catalog.return_value = get_fake_catalog()
        exporter = ContentMetadataExporter('fake-user', self.config)
        exporter.export()
        assert mock_ent_catalog_api.called
        assert mock_ent_catalog_api.return_value.get_enterprise_catalog.call_args[0][0] == \
            self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_args[0][0] == [get_fake_catalog()]

        enterprise_catalog_data = {
            'uuid': str(self.enterprise_customer_catalog.uuid),
            'title': self.enterprise_customer_catalog.title,
            'enterprise_customer': str(self.enterprise_customer_catalog.enterprise_customer.uuid),
            'catalog_query_uuid': str(self.enterprise_customer_catalog.enterprise_catalog_query.uuid),
            'content_last_modified': str(self.enterprise_customer_catalog.enterprise_catalog_query.modified),
            'catalog_modified': str(self.enterprise_customer_catalog.modified)
        }
        mock_ent_catalog_api.return_value.get_enterprise_catalog.return_value = enterprise_catalog_data
        self.config.catalogs_to_transmit = str(self.enterprise_customer_catalog.uuid)
        self.config.save()
        exporter.export()
        assert mock_ent_catalog_api.return_value.get_enterprise_catalog.call_count == 2
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_count == 2
        # 'catalogs_to_transmit' argument has valid uuid so only that catalog will be transmitted.
        assert mock_ent_catalog_api.return_value.get_enterprise_catalog.call_args[0][0] == \
            self.config.customer_catalogs_to_transmit.first().uuid
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_args[0][0] == [enterprise_catalog_data]

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_bad_data_transform_mapping(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` raises an exception when DATA_TRANSFORM_MAPPING is invalid.
        """
        mock_api_client.return_value.get_content_metadata.return_value = get_fake_content_metadata(), {}
        mock_api_client.return_value.get_enterprise_catalog.return_value = get_fake_catalog()
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING['fake-key'] = 'fake-value'
        exporter = ContentMetadataExporter('fake-user', self.config)
        with LogCapture(level=logging.ERROR) as log_capture:
            exporter.export()
            expected_message = 'Failed to transform content metadata item field [{}] for [{}]'.format(
                'fake-value',
                self.enterprise_customer_catalog.enterprise_customer.name
            )
            assert expected_message in log_capture.records[0].getMessage()

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_export_fetches_content_only_when_update_needed(self, mock_ent_catalog_api):
        """
        Test that when a ContentMetadataItemTransmission exists with a `catalog_last_changed` field that comes after the
        last modified time of content's associated catalog, we don't fetch the catalog's metadata.
        """
        # Generate a past transmission item that will indicate no updated needed
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            integrated_channel_code=self.config.channel_code(),
            catalog_last_changed='2021-07-16T15:11:10.521611Z'
        )
        mock_ent_catalog_api.return_value.get_content_metadata.return_value = get_fake_content_metadata(), {}
        mock_ent_catalog_api.return_value.get_enterprise_catalog.return_value = get_fake_catalog()
        exporter = ContentMetadataExporter('fake-user', self.config)
        payload = exporter.export()
        assert len(payload) == 0
        # We should make a call for the enterprise catalog, but no call for the metadata because no update needed
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_count == 0
        assert mock_ent_catalog_api.return_value.get_enterprise_catalog.call_count == 1
