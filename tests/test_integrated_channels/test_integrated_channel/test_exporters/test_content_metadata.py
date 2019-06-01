# -*- coding: utf-8 -*-
"""
Tests for the base content metadata exporter.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import logging
import unittest

import mock
import responses
from pytest import mark
from testfixtures import LogCapture

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``ContentMetadataExporter`` class.
    """

    def setUp(self):
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

    @responses.activate
    def test_content_exporter_export(self):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        exporter = ContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

    @responses.activate
    def test_content_exporter_bad_data_transform_mapping(self):
        """
        ``ContentMetadataExporter``'s ``export`` raises an exception when DATA_TRANSFORM_MAPPING is invalid.
        """
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING['fake-key'] = 'fake-value'
        exporter = ContentMetadataExporter('fake-user', self.config)
        with LogCapture(level=logging.ERROR) as log_capture:
            exporter.export()
            expected_message = 'Failed to transform content metadata item field [{}] for [{}]'.format(
                'fake-value',
                self.enterprise_customer_catalog.enterprise_customer.name
            )
            assert expected_message in log_capture.records[0].getMessage()
