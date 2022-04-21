"""
Tests for Canvas content metadata exporters.
"""

import unittest
from unittest import mock

import ddt
import responses
from pytest import mark

from integrated_channels.canvas.exporters.content_metadata import CanvasContentMetadataExporter
from test_utils import factories
from test_utils.fake_catalog_api import (
    FAKE_COURSE,
    FAKE_COURSE_RUN,
    get_fake_catalog_diff_create,
    get_fake_content_metadata,
)
from test_utils.fake_enterprise_api import EnterpriseMockMixin

GENERIC_CONTENT_METADATA_ITEM = {
    'enrollment_url': 'http://some/enrollment/url/',
    'aggregation_key': 'course:edX+DemoX',
    'title': 'edX Demonstration Course',
    'key': 'edX+DemoX',
    'content_type': 'course',
}


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
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``CanvasContentMetadataExporter``'s ``export`` produces the expected export.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()

        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload, content_updated_mapping = exporter.export()
        for key in create_payload:
            assert key in [FAKE_COURSE_RUN['key'], FAKE_COURSE['key']]
            assert key in content_updated_mapping
        assert not update_payload
        assert not delete_payload

        for item in create_payload.values():
            self.assertTrue(
                {'syllabus_body', 'default_view', 'name'}
                .issubset(set(item.keys()))
            )

    @ddt.data(
        (
            {},
            None
        ),
        (
            {
                'end': 'test_end_string'
            },
            'test_end_string'
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_end(self, content_metadata_item, expected_end_value):
        """
        ``CanvasContentMetadataExporter``'s ``transform_end`` returns string passed in from
        Content metadata or None if no 'end' field present on content_metadata_item.
        """
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        end = exporter.transform_end(content_metadata_item)
        assert end == expected_end_value

    @ddt.data(
        (
            {},
            None
        ),
        (
            {
                'start': 'test_start_string'
            },
            'test_start_string'
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_start(self, content_metadata_item, expected_start_value):
        """
        ``CanvasContentMetadataExporter``'s ``transform_start`` returns string passed in from
        Content metadata or None if no 'start' field present on content_metadata_item.
        """
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        start = exporter.transform_start(content_metadata_item)
        assert start == expected_start_value

    @ddt.data(
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
            },
            '<a href=http://some/enrollment/url/>Go to edX course page</a><br />'
            'Detailed description of edx demo course. <br /><br />Starts: N/A<br />Ends: N/A'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
            },
            '<a href=http://some/enrollment/url/>Go to edX course page</a><br />'
            'edX Demonstration Course <br /><br />Starts: N/A<br />Ends: N/A'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
            },
            '<a href=http://some/enrollment/url/>Go to edX course page</a><br />'
            'Some short description. <br /><br />Starts: N/A<br />Ends: N/A'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/'
            },
            '<a href=http://some/enrollment/url/>Go to edX course page</a><br /> <br /><br />Starts: N/A<br />Ends: N/A'
        ),
        (
            {
                'enrollment_url': 'http://some/enrollment/url/',
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'start': '2011-01-01T01:00:00Z',
                'end': '2011-03-01T01:00:00Z'
            },
            ('<a href=http://some/enrollment/url/>Go to edX course page</a><br />Some short description. <br />'
             '<br />Starts: Sat Jan 01 2011 01:00:00<br />Ends: Tue Mar 01 2011 01:00:00')
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
        content_metadata_item = GENERIC_CONTENT_METADATA_ITEM
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_default_view(content_metadata_item) == 'syllabus'

    @responses.activate
    def test_transform_is_public(self):
        """
        `CanvasContentMetadataExporter``'s ``transform_is_public_view` returns True.
        """
        content_metadata_item = GENERIC_CONTENT_METADATA_ITEM
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_is_public(content_metadata_item) is True

    @responses.activate
    def test_transform_self_enrollment(self):
        """
        `CanvasContentMetadataExporter``'s ``transform_self_enrollment` returns True.
        """
        content_metadata_item = GENERIC_CONTENT_METADATA_ITEM
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_self_enrollment(content_metadata_item) is True

    @responses.activate
    def test_transform_indexed(self):
        """
        `CanvasContentMetadataExporter``'s ''transform_indexed` returns 1 as a value
        """
        content_metadata_item = GENERIC_CONTENT_METADATA_ITEM
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_indexed(content_metadata_item) == 1

    @responses.activate
    def test_transform_restrict_enrollments_to_course_dates(self):
        """
        `CanvasContentMetadataExporter``'s ''transform_restrict_enrollments_to_course_dates` returns True as a value
        """
        content_metadata_item = GENERIC_CONTENT_METADATA_ITEM
        exporter = CanvasContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_restrict_enrollments_to_course_dates(content_metadata_item) is True
