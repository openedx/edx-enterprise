# -*- coding: utf-8 -*-
"""
Tests for the base content metadata exporter.
"""

import logging
import unittest

import mock
import responses
from pytest import mark
from testfixtures import LogCapture

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import get_fake_content_metadata
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
        super(TestContentMetadataExporter, self).setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    def test_content_exporter_export(self, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        exporter = ContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

    @mock.patch("enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata")
    def test_export_with_catalogs_to_transmit(self, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        exporter = ContentMetadataExporter('fake-user', self.config)
        exporter.export()
        assert mock_get_content_metadata.called
        assert mock_get_content_metadata.call_args[0][0] == self.enterprise_customer_catalog.enterprise_customer
        # 'catalogs_to_transmit' argument was empty list so all the catalogs will be transmitted.
        assert mock_get_content_metadata.call_args[1]['enterprise_catalogs'] == []

        self.config.catalogs_to_transmit = str(self.enterprise_customer_catalog.uuid)
        self.config.save()
        exporter.export()
        assert mock_get_content_metadata.called
        assert mock_get_content_metadata.call_args[0][0] == self.enterprise_customer_catalog.enterprise_customer
        # 'catalogs_to_transmit' argument has valid uuid so only that catalog will be transmitted.
        assert mock_get_content_metadata.call_args[1]['enterprise_catalogs'].first().uuid == \
            self.config.customer_catalogs_to_transmit.first().uuid

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_bad_data_transform_mapping(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` raises an exception when DATA_TRANSFORM_MAPPING is invalid.
        """
        mock_api_client.return_value.get_content_metadata.return_value = get_fake_content_metadata()
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING['fake-key'] = 'fake-value'
        exporter = ContentMetadataExporter('fake-user', self.config)
        with LogCapture(level=logging.ERROR) as log_capture:
            exporter.export()
            expected_message = 'Failed to transform content metadata item field [{}] for [{}]'.format(
                'fake-value',
                self.enterprise_customer_catalog.enterprise_customer.name
            )
            assert expected_message in log_capture.records[0].getMessage()
