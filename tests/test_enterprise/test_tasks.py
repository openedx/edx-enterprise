# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tasks module.
"""

import unittest

import mock
from pytest import mark

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseEnrollmentSource
from enterprise.tasks import create_enterprise_enrollment
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class TestEnterpriseTasks(unittest.TestCase):
    """
    Tests tasks associated with Enterprise.
    """
    FAKE_COURSE_ID = 'course-v1:edx+Test+2T2019'

    def setUp(self):
        """
        Setup for `TestEnterpriseTasks` test.
        """
        self.user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        super().setUp()

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_in_catalog(self, mock_contains_course):
        """
        Task should create an enterprise enrollment if the course_id handed to
        the function is part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = True
        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_source_set(self, mock_contains_course):
        """
        Task should create an enterprise enrollment if the course_id handed to
        the function is part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = True
        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1
        assert EnterpriseCourseEnrollment.objects.get(
            course_id=self.FAKE_COURSE_ID,
        ).source.slug == EnterpriseEnrollmentSource.ENROLLMENT_TASK

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_not_in_catalog(self, mock_contains_course):
        """
        Task should NOT create an enterprise enrollment if the course_id handed
        to the function is NOT part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = False

        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 0

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    def test_create_enrollment_task_no_create_duplicates(self, catalog_api_client_mock):
        """
        Task should return without creating a new EnterpriseCourseEnrollment
        if one with the course_id and enterprise_customer_user specified
        already exists.
        """
        EnterpriseCourseEnrollment.objects.create(
            course_id=self.FAKE_COURSE_ID,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        catalog_api_client_mock.return_value.contains_content_items.return_value = False

        assert EnterpriseCourseEnrollment.objects.count() == 1
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1
