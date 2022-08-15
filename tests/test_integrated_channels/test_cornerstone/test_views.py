"""
Tests for Cornerstone views.
"""

import datetime
from unittest import mock

import responses
from dateutil import parser
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings
from django.utils.http import http_date

from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import APITest, factories
from test_utils.fake_catalog_api import (
    get_fake_catalog_diff_create_w_program,
    get_fake_catalog_diff_w_one_each_2,
    get_fake_content_metadata,
    get_fake_content_metadata_for_create_w_program,
    get_fake_content_metadata_for_partial_create_w_program,
)
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestCornerstoneCoursesListView(APITest, EnterpriseMockMixin):
    """
    Tests for the ``CornerstoneCoursesListView`` class.
    """
    def setUp(self):
        courses_list_endpoint = reverse('cornerstone-course-list')
        self.course_list_url = settings.TEST_SERVER + courses_list_endpoint
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        super().setUp()

    def test_course_list_unauthorized_non_customer(self):
        """
        Verify the contains_content_items endpoint rejects users that are not catalog learners
        """
        self.client.logout()
        response = self.client.get(self.course_list_url)
        self.assertEqual(response.status_code, 401)

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
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_course_list_with_skip_key_if_none_false(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        Test courses list view produces desired json when SKIP_KEY_IF_NONE is set to False
        """
        # get content metadata returns a list of three pieces of content to create, a course, a course run and a program
        # these pieces of content cannot exist as a record
        mock_get_content_metadata.return_value = get_fake_content_metadata_for_create_w_program()
        # get catalog diff returns the same three items in the create bucket, as the system will request the metadata on
        # all pieces of content that it needs to update or create
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create_w_program()

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
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_course_list(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        Test courses list view produces desired json
        """
        # get content metadata returns a list of three pieces of content to create, a course, a course run and a program
        # these pieces of content cannot exist as a record
        mock_get_content_metadata.return_value = get_fake_content_metadata_for_create_w_program()
        # get catalog diff returns the same three items in the create bucket, as the system will request the metadata on
        # all pieces of content that it needs to update or create
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create_w_program()

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

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_course_list_last_modified(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        Test courses list view produces desired json
        """
        # get content metadata returns a list of three pieces of content to create, a course, a course run and a program
        # these pieces of content cannot exist as a record
        mock_get_content_metadata.return_value = get_fake_content_metadata_for_create_w_program()
        # get catalog diff returns the same three items in the create bucket, as the system will request the metadata on
        # all pieces of content that it needs to update or create
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create_w_program()

        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_list_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid
        )
        if_modified_since = http_date(int(round(datetime.datetime.now().timestamp() - 300)))
        response = self.client.get(url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        for item in response.data:
            assert parser.parse(item['LastModifiedUTC']) >= parser.parse(if_modified_since)

        created_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        assert len(created_transmissions) == len(get_fake_content_metadata())

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_course_list_restricted_count(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        Test courses list view produces desired json
        """
        # get content metadata returns a list of three pieces of content to create, a course, a course run and a program
        # these pieces of content cannot exist as a record
        mock_get_content_metadata.return_value = get_fake_content_metadata_for_create_w_program()
        # get catalog diff returns the same three items in the create bucket, as the system will request the metadata on
        # all pieces of content that it needs to update or create
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create_w_program()
        url = '{path}?ciid={customer_uuid}'.format(
            path=self.course_list_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid
        )
        # not testing if-modified specifically but want to make sure counts work with this header
        if_modified_since = http_date(int(round(datetime.datetime.now().timestamp() - 300)))
        response = self.client.get(url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 3 creates, no count restriction, so expect 3
        self.assertEqual(len(response.data), 3)
        created_transmissions = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        assert len(created_transmissions) == len(get_fake_content_metadata_for_create_w_program())

        # change the content last changed of the records so an update can be detected
        created_transmissions.update(content_last_changed=None)
        # mock both the content metadata list end point and the catalog diff endpoint to return 1 create, 1 update, 1
        # delete. This means the get content metadata endpoint is returning two pieces of content one for the update and
        # one for the create. The course that the diff endpoint says to create cannot already exist in the DB.
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_w_one_each_2()
        mock_get_content_metadata.return_value = get_fake_content_metadata_for_partial_create_w_program()
        response = self.client.get(url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 1 create, 1 update, 1 delete, so expect 3
        self.assertEqual(len(response.data), 3)
        url = '{path}?ciid={customer_uuid}&count={count}'.format(
            path=self.course_list_url,
            customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid,
            count=1
        )
        # change the content last changed of the records so an update can be detected
        created_transmissions.update(content_last_changed=None)

        # Re-request and expect the create to be already created so the only item to be returned is the update item
        response = self.client.get(url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 1 create, 1 update, 1 delete, count set to 1, so expect 1
        self.assertEqual(len(response.data), 1)
