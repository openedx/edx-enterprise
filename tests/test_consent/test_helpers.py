# -*- coding: utf-8 -*-
"""
Tests for helper functions in the Consent application.
"""

import ddt
import mock
from pytest import mark

from django.test import testcases

from consent import helpers
from test_utils import TEST_UUID


@mark.django_db
@ddt.ddt
class ConsentHelpersTest(testcases.TestCase):
    """
    Test cases for helper functions for the Consent application.
    """
    def setUp(self):
        self.fake_course_id = 'fake-course'
        super().setUp()

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_data_sharing_consent_no_enterprise(self, mock_catalog_api_class):
        """
        Test that the returned consent record is None when no EnterpriseCustomer exists.
        """
        mock_catalog_api_class = mock_catalog_api_class.return_value
        mock_catalog_api_class.get_course_id.return_value = self.fake_course_id
        assert helpers.get_data_sharing_consent('bob', TEST_UUID, course_id=self.fake_course_id) is None
