# -*- coding: utf-8 -*-
"""
Tests for Moodle content metadata exporters.
"""

import unittest

import ddt
import mock
import responses
from pytest import mark

from integrated_channels.moodle.exporters.content_metadata import MoodleContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import get_fake_content_metadata
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestMoodleContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``MoodleContentMetadataExporter`` class.
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestMoodleContentMetadataExporter, self).setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    def test_content_exporter_export(self, mock_get_content_metadata):
        """
        ``MoodleContentMetadataExporter``'s ``export`` produces the expected export.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])
        for item in content_items.values():
            self.assertTrue(
                set(['categoryid', 'summary'])
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
        ``MoodleContentMetadataExporter``'s ``transform_description`` returns correct syllabus_body
        """
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        description = exporter.transform_description(content_metadata_item)
        assert description == expected_description

    @responses.activate
    def test_transform_start(self):
        """
        `MoodleContentMetadataExporter``'s ``transform_start` returns int timestamp.
        """
        content_metadata_item = {
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoX',
            'content_type': 'course',
            'start': '2030-01-01T00:00:00Z',
            'end': '2030-03-01T00:00:00Z'
        }
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_start(content_metadata_item) == 1893456000  # Jan 1, 2030 UTC

    @responses.activate
    def test_transform_end(self):
        """
        `MoodleContentMetadataExporter``'s ``transform_start` returns int timestamp.
        """
        content_metadata_item = {
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoX',
            'content_type': 'course',
            'start': '2030-01-01T00:00:00Z',
            'end': '2030-03-01T00:00:00Z'
        }
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_end(content_metadata_item) == 1898553600  # Jan 1, 2030 UTC
