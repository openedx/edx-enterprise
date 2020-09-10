# -*- coding: utf-8 -*-
"""
Tests for Canvas content metadata exporters.
"""

import unittest

import ddt
import mock
import responses
from pytest import mark

from enterprise.constants import ContentType
from integrated_channels.canvas.exporters.content_metadata import CanvasContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import get_fake_content_metadata
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestCanvasContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``CanvasContentMetadataExporter`` class.
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestCanvasContentMetadataExporter, self).setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    def test_content_exporter_export(self, mock_get_content_metadata):
        """
        ``CanvasContentMetadataExporter``'s ``export`` produces the expected export.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

        for item in content_items.values():
            self.assertTrue(
                set(['syllabus_body', 'default_view', 'name'])
                .issubset(set(item.channel_metadata.keys()))
            )

    @ddt.data(
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
            },
            '<a href=http://some/enrollment/url/>To edX Course Page</a><br />Detailed description of edx demo course.'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
            },
            '<a href=http://some/enrollment/url/>To edX Course Page</a><br />edX Demonstration Course'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
            },
            '<a href=http://some/enrollment/url/>To edX Course Page</a><br />Some short description.'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/'
            },
            '<a href=http://some/enrollment/url/>To edX Course Page</a><br />'
        )

    )
    @responses.activate
    @ddt.unpack
    def test_transform_description_includes_url(self, content_metadata_item, expected_description):
        """
        ``CanvasContentMetadataExporter``'s ``transform_description`` returns correct syllabus_body
        """
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        description = exporter.transform_description(content_metadata_item)
        assert description == expected_description

    @responses.activate
    def test_transform_default_view(self):
        """
        `CanvasContentMetadataExporter``'s ``transform_default_view` returns syllabus as value.
        """
        content_metadata_item = {
            'enrollment_url': 'http://some/enrollment/url/',
            'aggregation_key': 'course:edX+DemoX',
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoX',
            ContentType.METADATA_KEY: ContentType.COURSE,
        }
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_default_view(content_metadata_item) == 'syllabus'
