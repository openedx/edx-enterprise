# -*- coding: utf-8 -*-
"""
Tests for Cornerstone views.
"""

import mock
import responses
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings
from django.utils import dateparse

from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import APITest, factories
from test_utils.fake_catalog_api import get_fake_catalog, get_fake_content_metadata
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestCornerstoneCoursesListView(APITest, EnterpriseMockMixin):
    """
    Tests for the ``CornerstoneCoursesListView`` class.
    """
    def setUp(self):
        courses_list_endpoint = reverse('cornerstone-course-list')
        courses_updates_endpoint = reverse('cornerstone-course-updates')
        self.course_list_url = settings.TEST_SERVER + courses_list_endpoint
        self.course_updates_url = settings.TEST_SERVER + courses_updates_endpoint
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super().setUp()

    @responses.activate
    def test_course_list_without_ciid(self):
        """
        Test courses list view without ciid query parameter
        """
        response = self.client.get(self.course_list_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @responses.activate
    def test_course_list_invalid_ciid(self):
        """
        Test courses list with ciid of non-existing customer
        """
        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_list_url,
            customer_uuid='a00c0def-0c00-0000-a860-b7cd772e0000'
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_enterprise_catalog')
    def test_course_list_with_skip_key_if_none_false(self, mock_get_enterprise_catalog, mock_get_content_metadata):
        """
        Test courses list view produces desired json when SKIP_KEY_IF_NONE is set to False
        """
        fake_content_metadata = get_fake_content_metadata()
        fake_catalog = get_fake_catalog()
        fake_catalog_modified_at = max(
            fake_catalog['content_last_modified'], fake_catalog['catalog_modified']
        )
        fake_catalogs_last_modified = {
            get_content_metadata_item_id(
                content_metadata
            ): fake_catalog_modified_at for content_metadata in fake_content_metadata
        }
        mock_get_content_metadata.return_value = fake_content_metadata, fake_catalogs_last_modified
        mock_get_enterprise_catalog.return_value = fake_catalog
        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_list_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid
        )
        with mock.patch(
                'integrated_channels.cornerstone.models.CornerstoneContentMetadataExporter.SKIP_KEY_IF_NONE',
                new_callable=mock.PropertyMock
        ) as mock_skip_key_if_none:
            mock_skip_key_if_none.return_value = False
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 3)
            keys = {key for item in response.data for key in item.keys()}
            expected_keys = [
                "ID", "URL", "IsActive", "LastModifiedUTC", "Title", "Description",
                "Thumbnail", "Duration", "Partners", "Languages", "Subjects",
            ]
            for key in expected_keys:
                self.assertIn(key, keys)

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    def test_course_list(self, mock_get_content_metadata):
        """
        Test courses list view produces desired json
        """
        fake_content_metadata = get_fake_content_metadata()
        mock_last_modified = {
            get_content_metadata_item_id(content_metadata): None for content_metadata in fake_content_metadata
        }
        mock_get_content_metadata.return_value = fake_content_metadata, mock_last_modified

        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_list_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        keys = {key for item in response.data for key in item.keys()}
        expected_keys = [
            "ID", "URL", "IsActive", "LastModifiedUTC", "Title", "Description",
            "Thumbnail", "Partners", "Languages", "Subjects",
        ]
        for key in expected_keys:
            self.assertIn(key, keys)

        # required fields should not be empty
        required_keys = ["Partners", "Languages", "Subjects"]
        for item in response.data:
            for key in required_keys:
                self.assertTrue(item[key])

        created_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        assert len(created_transmissions) == len(get_fake_content_metadata())
        for transmission_item in created_transmissions:
            assert transmission_item.catalog_last_changed is None

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_enterprise_catalog')
    def test_course_updates(self, mock_get_enterprise_catalog, mock_get_content_metadata):
        """
        Test courses updates view produces desired json and saves transmission items
        """
        fake_content_metadata = get_fake_content_metadata()
        test_modified_datetime = '2020-07-16T15:11:10.521611Z'
        catalogs_last_modified = {
            get_content_metadata_item_id(
                content_metadata
            ): test_modified_datetime for content_metadata in fake_content_metadata
        }
        mock_get_content_metadata.return_value = fake_content_metadata, catalogs_last_modified
        mock_get_enterprise_catalog.return_value = get_fake_catalog()
        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_updates_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        keys = {key for item in response.data for key in item.keys()}
        expected_keys = [
            "ID", "URL", "IsActive", "LastModifiedUTC", "Title", "Description",
            "Thumbnail", "Partners", "Languages", "Subjects",
        ]
        for key in expected_keys:
            self.assertIn(key, keys)

        # required fields should not be empty
        required_keys = ["Partners", "Languages", "Subjects"]
        for item in response.data:
            for key in required_keys:
                self.assertTrue(item[key])
        created_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        assert len(created_transmissions) == len(fake_content_metadata)
        for transmission_item in created_transmissions:
            assert transmission_item.catalog_last_changed == dateparse.parse_datetime(test_modified_datetime)
