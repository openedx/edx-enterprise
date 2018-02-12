# -*- coding: utf-8 -*-
"""
Tests for Degreed content metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
import responses
from pytest import mark

from integrated_channels.degreed.exporters.content_metadata import DegreedContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestDegreedContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``DegreedContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_ent_courses_api_with_pagination(
            str(self.enterprise_customer_catalog.enterprise_customer.uuid),
            ['course-v1:edX+DemoX+Demo_Course']
        )
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestDegreedContentMetadataExporter, self).setUp()

    @responses.activate
    def test_content_exporter_export(self):
        """
        ``DegreedContentMetadataExporter``'s ``export`` produces the expected export.
        """
        exporter = DegreedContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])
