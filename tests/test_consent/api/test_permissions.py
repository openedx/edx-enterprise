# -*- coding: utf-8 -*-
"""
Tests for the Consent application's` API permissions.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from consent.api.v1.views import DataSharingConsentView as DSCView
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from django.conf import settings

from test_utils import TEST_COURSE, TEST_PASSWORD, TEST_USER_ID, TEST_USERNAME, TEST_UUID, APITest, factories


@ddt.ddt
class TestConsentAPIPermissions(APITest):
    """
    Tests for Consent API permissions.
    """

    DSC_ENDPOINT = reverse('data_sharing_consent')
    DSC_PATH = settings.TEST_SERVER + DSC_ENDPOINT
    FAKE_REQUEST_BODY = {
        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
        DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
    }

    def setUp(self):
        """
        Perform operations common to all tests.
        """
        self.create_user(username=TEST_USERNAME, password=TEST_PASSWORD, id=TEST_USER_ID)
        self.client = APIClient()
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        discovery_client_class = mock.patch('enterprise.models.CourseCatalogApiServiceClient')
        self.discovery_client = discovery_client_class.start().return_value
        self.discovery_client.is_course_in_catalog.return_value = True
        self.addCleanup(discovery_client_class.stop)
        factories.DataSharingConsentFactory.create(
            course_id=TEST_COURSE,
            username=TEST_USERNAME,
            enterprise_customer__uuid=TEST_UUID
        )

    @ddt.data(
        (TEST_USERNAME, True, status.HTTP_200_OK),
        ('someone_else', True, status.HTTP_200_OK),
        (TEST_USERNAME, False, status.HTTP_200_OK),
        ('someone_else', False, status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_is_staff_or_user_in_request_permissions(self, username, is_staff, expected_status):
        if username != self.FAKE_REQUEST_BODY[DSCView.REQUIRED_PARAM_USERNAME]:
            # Requester is not user in request, so create him.
            self.create_user(username=username, is_staff=is_staff, password=TEST_PASSWORD, id=2)
            self.client.login(username=username, password=TEST_PASSWORD)
        response = self.client.get(self.DSC_PATH, self.FAKE_REQUEST_BODY)
        self.client.post(self.DSC_PATH, self.FAKE_REQUEST_BODY)  # For coverage of not-GET case.
        self.assertEqual(response.status_code, expected_status)
