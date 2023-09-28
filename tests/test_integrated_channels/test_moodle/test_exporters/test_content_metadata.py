"""
Tests for Moodle content metadata exporters.
"""

import unittest
from unittest import mock

import ddt
import responses
from pytest import mark

from integrated_channels.moodle.exporters.content_metadata import MoodleContentMetadataExporter
from test_utils import factories
from test_utils.fake_catalog_api import (
    FAKE_COURSE,
    FAKE_COURSE_RUN,
    get_fake_catalog_diff_create,
    get_fake_content_metadata_no_program,
)
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
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``MoodleContentMetadataExporter``'s ``export`` produces the expected export.
        """
        fake_content_metadata = get_fake_content_metadata_no_program()
        mock_get_content_metadata.return_value = fake_content_metadata
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        for key in create_payload:
            assert key in [FAKE_COURSE_RUN['key'], FAKE_COURSE['key']]
        assert not update_payload
        assert not delete_payload

    @ddt.data(
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
            },
            '<a href=http://some/enrollment/url/ target="_blank">Go to edX course page</a><br />'
            'Detailed description of edx demo course.'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
            },
            '<a href=http://some/enrollment/url/ target="_blank">Go to edX course page</a><br />'
            'edX Demonstration Course'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
            },
            '<a href=http://some/enrollment/url/ target="_blank">Go to edX course page</a><br />Some short description.'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/'
            },
            '<a href=http://some/enrollment/url/ target="_blank">Go to edX course page</a><br />'
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
        `MoodleContentMetadataExporter``'s ``transform_start`` returns int timestamp.
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
        `MoodleContentMetadataExporter``'s ``transform_end`` returns int timestamp.
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

    @responses.activate
    def test_transform_shortname(self):
        """
        `MoodleContentMetadataExporter``'s ``transform_shortname`` returns
        a str combination  of title and key.
        """
        content_metadata_item = {
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoXT0220'
        }
        expected_name = '{} ({})'.format(content_metadata_item['title'], content_metadata_item['key'])
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_shortname(content_metadata_item) == expected_name

    @responses.activate
    def test_transform_title(self):
        """
        `MoodleContentMetadataExporter``'s ``transform_title`` returns a str
        featuring the title and partners/organizations
        """
        content_metadata_item = {
            'title': 'edX Demonstration Course',
            'organizations': [
                'HarvardX:Harvard University',
                'MIT:MIT'
            ]
        }
        expected_title = '{} ({})'.format(
            '{} - via edX.org'.format(content_metadata_item['title']),
            ', '.join(content_metadata_item['organizations'])
        )
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_title(content_metadata_item) == expected_title

    @responses.activate
    def test_apply_delete_transformation(self):
        """
        `MoodleContentMetadataExporter``'s ``transform_title`` returns a str
        featuring the title and partners/organizations
        """
        content_metadata_item = {
            'title': 'edX Demonstration Course'
        }
        exporter = MoodleContentMetadataExporter('fake-user', self.config)
        transformed_metada_data = exporter._apply_delete_transformation(content_metadata_item)
        assert transformed_metada_data['visible'] == 0

