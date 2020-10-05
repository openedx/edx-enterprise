# -*- coding: utf-8 -*-
"""
Tests for Blackboard content metadata exporters.
"""

import unittest

import mock
import responses
from pytest import mark
from collections import OrderedDict

from integrated_channels.blackboard.exporters.content_metadata import BlackboardContentMetadataExporter

from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import FAKE_COURSE_RUN, FAKE_COURSE
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestBlackboardContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``BlackboardContentMetadataExporter`` class.
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        self.config = factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestBlackboardContentMetadataExporter, self).setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    def test_content_exporter_export(self, mock_get_content_metadata):
        """
        ``BlackboardContentMetadataExporter``'s ``export`` produces the expected export.
        """
        fake_content_metadata = OrderedDict()
        fake_content_metadata[FAKE_COURSE_RUN['key']] = FAKE_COURSE_RUN
        fake_content_metadata[FAKE_COURSE['key']] = FAKE_COURSE

        mock_get_content_metadata.return_value = list(fake_content_metadata.values())
        exporter = BlackboardContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()

        # not testing with program content type yet (it just generates a lot of keyError)
        assert sorted(list(content_items.keys())) == sorted([
            FAKE_COURSE_RUN['key'],
            FAKE_COURSE['key'],
        ])

        expected_keys = [field for field in exporter.DATA_TRANSFORM_MAPPING.keys()]
        for item in content_items.values():
            self.assertTrue(
                set(expected_keys)
                .issubset(set(item.channel_metadata.keys()))
            )
