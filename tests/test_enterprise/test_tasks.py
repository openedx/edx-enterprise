# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tasks module.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import mock
from pytest import mark

from enterprise.models import EnterpriseCourseEnrollment
from enterprise.tasks import create_enterprise_enrollment
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class TestEnterpriseTasks(unittest.TestCase):
    """
    Tests tasks associated with Enterprise.
    """
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
        super(TestEnterpriseTasks, self).setUp()

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_in_catalog(self, mock_contains_course):
        """
        Task should create an enterprise enrollment if the course_id handed to
        the function is part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = True

        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            'fake:course',
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_not_in_catalog(self, mock_contains_course):
        """
        Task should NOT create an enterprise enrollment if the course_id handed
        to the function is NOT part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = False

        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            'fake:course',
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 0

    def test_create_enrollment_task_no_create_duplicates(self):
        """
        Task should return without creating a new EnterpriseCourseEnrollment
        if one with the course_id and enterprise_customer_user specified
        already exists.
        """
        EnterpriseCourseEnrollment.objects.create(
            course_id='fake:course',
            enterprise_customer_user=self.enterprise_customer_user,
        )

        assert EnterpriseCourseEnrollment.objects.count() == 1
        create_enterprise_enrollment(
            'fake:course',
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1
