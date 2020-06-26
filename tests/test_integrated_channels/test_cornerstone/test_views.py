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

from test_utils import APITest, factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestCornerstoneCoursesListView(APITest, EnterpriseMockMixin):
    """
    Tests for the ``CornerstoneCoursesListView`` class.
    """
    def setUp(self):
        courses_list_endpoint = reverse('cornerstone-course-list')
        self.course_list_url = settings.TEST_SERVER + courses_list_endpoint
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
        super(TestCornerstoneCoursesListView, self).setUp()

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

    @responses.activate
    def test_course_list_with_skip_key_if_none_false(self):
        """
        Test courses list view produces desired json when SKIP_KEY_IF_NONE is set to False
        """
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
                "Thumbnail", "Duration", "Owners", "Languages", "Subjects",
            ]
            for key in expected_keys:
                self.assertIn(key, keys)

    @responses.activate
    def test_course_list(self):
        """
        Test courses list view produces desired json
        """
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
            "Thumbnail", "Owners", "Languages", "Subjects",
        ]
        for key in expected_keys:
            self.assertIn(key, keys)

        # required fields should not be empty
        required_keys = ["Owners", "Languages", "Subjects"]
        for item in response.data:
            for key in required_keys:
                self.assertTrue(item[key])
