# -*- coding: utf-8 -*-
"""
Tests for the djagno management command `create_enterprise_course_enrollments`.
"""
from __future__ import absolute_import, unicode_literals

import ddt
import mock
from pytest import mark

from django.core.management import call_command
from django.test import TestCase

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseEnrollmentSource
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
@ddt.ddt
class CreateEnterpriseCourseEnrollmentCommandTests(TestCase):
    """
    Test command `create_enterprise_course_enrollments`.
    """
    command = 'create_enterprise_course_enrollments'

    def setUp(self):
        self.course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )
        super(CreateEnterpriseCourseEnrollmentCommandTests, self).setUp()

    def mock_db_connection(self, connection_mock):
        """
        Set up db connection mock.
        """
        description = mock.MagicMock()
        description.__iter__.return_value = (('user_id',), ('enterprise_customer_uuid',), ('course_run_id',))
        fetchall = mock.MagicMock()
        fetchall.__iter__.return_value = [(self.user.id, self.enterprise_customer.uuid, self.course_run_id)]
        connection_mock.cursor.return_value = mock.MagicMock(
            __enter__=mock.MagicMock(
                return_value=mock.MagicMock(
                    description=description,
                    fetchall=mock.MagicMock(
                        side_effect=lambda: fetchall
                    )
                )
            )
        )

    @mock.patch.object(EnterpriseCustomer, 'catalog_contains_course', mock.Mock(side_effect=lambda x: True))
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.connection')
    @ddt.data(True, False)
    def test_enrollments_created(self, filter_by_enterprise_customer, connection_mock, logger_mock):
        """
        Test that the command creates missing EnterpriseCourseEnrollment records.
        """
        self.mock_db_connection(connection_mock)
        kwargs = {}
        if filter_by_enterprise_customer:
            kwargs['enterprise_customer_uuid'] = self.enterprise_customer.uuid

        call_command(self.command, **kwargs)
        course_enrollments = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_run_id
        )

        assert course_enrollments.count() == 1
        assert course_enrollments[0].source.slug == EnterpriseEnrollmentSource.MANAGEMENT_COMMAND
        logger_mock.info.assert_called_with('Created %s missing EnterpriseCourseEnrollments.', 1)

    @mock.patch.object(EnterpriseCustomer, 'catalog_contains_course', mock.Mock(side_effect=lambda x: False))
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.connection')
    def test_course_not_in_catalog(self, connection_mock, logger_mock):
        """
        Test that the command does not create missing EnterpriseCourseEnrollment records when
        the enrolled course is not in the catalog.
        """
        self.mock_db_connection(connection_mock)

        call_command(self.command)

        count = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_run_id
        ).count()

        assert count == 0
        logger_mock.info.assert_called_with('Created %s missing EnterpriseCourseEnrollments.', 0)

    @mock.patch.object(EnterpriseCustomer, 'catalog_contains_course', mock.Mock(side_effect=lambda x: True))
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.connection')
    def test_existing_enterprise_course_enrollment(self, connection_mock, logger_mock):
        """
        Test that the command does not create missing EnterpriseCourseEnrollment records when
        the enrolled course is not in the catalog.
        """
        self.mock_db_connection(connection_mock)
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_run_id
        )

        call_command(self.command)

        course_enrollments = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_run_id
        )

        assert course_enrollments.count() == 1
        assert course_enrollments[0].source is None

        logger_mock.warning.assert_called_with(
            'EnterpriseCourseEnrollment exists: EnterpriseCustomer [%s] - User [%s] - CourseRun [%s]',
            self.enterprise_customer.uuid,
            self.user.id,
            self.course_run_id
        )
        logger_mock.info.assert_called_with('Created %s missing EnterpriseCourseEnrollments.', 0)
