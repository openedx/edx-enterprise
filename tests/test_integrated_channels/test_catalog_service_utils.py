# -*- coding: utf-8 -*-
"""
Tests for the catalog_service_utils used by integration channels.
"""

import unittest

import mock
import pytest
from opaque_keys import InvalidKeyError

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment, get_course_run_for_enrollment
from test_utils import factories

A_GOOD_COURSE_ID = "edX/DemoX/Demo_Course"
A_BAD_COURSE_ID = "this_shall_not_pass"
A_LMS_USER = "a_lms_user"


@pytest.mark.django_db
class TestCatalogServiceUtils(unittest.TestCase):
    """
    Tests for lms_utils
    """

    def setUp(self):
        self.username = A_LMS_USER
        self.user = factories.UserFactory(username=self.username)
        super().setUp()

    def _create_enrollment(self, enterprise_customer_user):
        """
        Create EnterpriseCourseEnrollmentFactory instance
        """
        an_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=3,
            enterprise_customer_user=enterprise_customer_user,
        )
        return an_enrollment

    @mock.patch('integrated_channels.catalog_service_utils.get_course_catalog_api_service_client')
    def test_get_course_id_for_enrollment_success(self, mock_get_catalog_client):
        mock_get_catalog_client.return_value.get_course_id.return_value = A_GOOD_COURSE_ID

        an_enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        an_enrollment = self._create_enrollment(an_enterprise_customer_user)

        assert get_course_id_for_enrollment(an_enrollment) == A_GOOD_COURSE_ID
        mock_get_catalog_client.assert_called_with(site=an_enterprise_customer_user.enterprise_customer.site)

    @mock.patch('integrated_channels.catalog_service_utils.get_course_catalog_api_service_client')
    def test_get_course_run_for_enrollment_success(self, mock_get_catalog_client):
        expected_course_run = {"estimated_hours": 4}
        mock_get_catalog_client.return_value.get_course_run.return_value = expected_course_run

        an_enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        an_enrollment = self._create_enrollment(an_enterprise_customer_user)

        assert get_course_run_for_enrollment(an_enrollment) == expected_course_run
        mock_get_catalog_client.assert_called_with(site=an_enterprise_customer_user.enterprise_customer.site)
