"""
Tests for Blackboard content metadata exporters.
"""

import unittest
from unittest import mock

from pytest import mark

from integrated_channels.blackboard.exporters.content_metadata import BlackboardContentMetadataExporter
from test_utils import factories
from test_utils.fake_catalog_api import (
    FAKE_COURSE,
    FAKE_COURSE_RUN,
    get_fake_catalog_diff_create,
    get_fake_content_metadata_no_program,
)
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
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``BlackboardContentMetadataExporter``'s ``export`` produces the expected export.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata_no_program()
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()

        exporter = BlackboardContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload, content_updated_mapping = exporter.export()

        # not testing with program content type yet (it just generates a lot of keyError)
        for key in create_payload:
            assert key in [FAKE_COURSE_RUN['key'], FAKE_COURSE['key']]
            assert key in content_updated_mapping
        assert not update_payload
        assert not delete_payload
        expected_keys = exporter.DATA_TRANSFORM_MAPPING.keys()
        for item in create_payload.values():
            self.assertTrue(
                set(expected_keys)
                .issubset(set(item.keys()))
            )

    def test_transform_course_metadata(self):
        content_metadata_item = {
            'title': 'test title',
            'key': 'test key',
            'enrollment_url': 'http://some/enrollment/url/',
            'short_description': 'short desc',
        }
        exporter = BlackboardContentMetadataExporter('fake-user', self.config)
        description = exporter.transform_course_metadata(content_metadata_item)
        expected_description = {
            'description': exporter.DESCRIPTION_TEXT_TEMPLATE.format(enrollment_url='http://some/enrollment/url/'),
            'name': content_metadata_item['title'],
            'externalId': content_metadata_item['key'],
        }

        assert description == expected_description

    def test_transform_course_child_content_metadata(self):
        content_metadata_item = {
            'title': 'edX Course Details',
            'enrollment_url': 'http://some/enrollment/url/',
            'full_description': 'short desc',
            'image_url': 'image_url',
        }
        exporter = BlackboardContentMetadataExporter('fake-user', self.config)
        description = exporter.transform_course_child_content_metadata(content_metadata_item)
        expected_description = {
            'title': content_metadata_item.get('title'),
            'availability': 'Yes',
            'contentHandler': {
                'id': 'resource/x-bb-document',
            },
            'body': exporter.COURSE_CONTENT_BODY_TEMPLATE.format(
                title=content_metadata_item.get('title'),
                description=content_metadata_item.get('full_description', None),
                image_url=content_metadata_item.get('image_url', None),
                enrollment_url=content_metadata_item.get('enrollment_url', None),
            )
        }
        assert description == expected_description
