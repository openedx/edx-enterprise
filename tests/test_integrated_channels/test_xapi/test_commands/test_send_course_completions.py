# -*- coding: utf-8 -*-
"""
Test xAPI management command to send course completion data.
"""

from __future__ import absolute_import, unicode_literals

import unittest
import uuid

import mock
from pytest import mark, raises

from django.core.management import CommandError, call_command

from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.exceptions import ClientError
from test_utils import factories

MODULE_PATH = 'integrated_channels.xapi.management.commands.send_course_completions.'


@mark.django_db
class TestSendCourseCompletions(unittest.TestCase):
    """
    Tests for the ``send_course_completions`` management command.
    """

    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    def test_parse_arguments(self):
        """
        Make sure command runs only when correct arguments are passed.
        """
        enterprise_uuid = str(uuid.uuid4())
        # Make sure CommandError is raised when enterprise customer with given uuid does not exist.
        with raises(
                CommandError,
                match='Enterprise customer with uuid "{enterprise_customer_uuid}" '
                      'does not exist.'.format(enterprise_customer_uuid=enterprise_uuid)
        ):
            call_command('send_course_completions', days=1, enterprise_customer_uuid=enterprise_uuid)

    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    def test_error_for_missing_lrs_configuration(self):
        """
        Make sure CommandError is raised if XAPILRSConfiguration does not exis for the given enterprise customer.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory()
        with raises(
                CommandError,
                match='No xAPI Configuration found for '
                      '"{enterprise_customer}"'.format(enterprise_customer=enterprise_customer.name)
        ):
            call_command('send_course_completions', days=1, enterprise_customer_uuid=enterprise_customer.uuid)

    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient', mock.MagicMock())
    def test_error_for_invalid_environment(self):
        """
        Make sure NotConnectedToOpenEdX is raised when enterprise app is not installed in Open edX environment.
        """
        xapi_config = factories.XAPILRSConfigurationFactory()

        with raises(
                NotConnectedToOpenEdX,
                match='This package must be installed in an OpenEdX environment.'
        ):
            call_command(
                'send_course_completions',
                days=1,
                enterprise_customer_uuid=xapi_config.enterprise_customer.uuid,
            )

    @mock.patch(
        MODULE_PATH + 'EnterpriseCustomerUser',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment',
        mock.MagicMock()
    )
    @mock.patch(MODULE_PATH + 'PersistentCourseGrade')
    def test_get_course_completions(self, mock_persistent_course_grade):
        """
        Make sure get_course_completions works as expected
        """
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        user = factories.UserFactory()
        enterprise_course_enrollments = [
            mock.Mock(id=42, user_id=user.id)
        ]
        Command.get_course_completions(enterprise_course_enrollments)
        assert mock_persistent_course_grade.objects.filter.called

        mock_persistent_course_grade.objects.filter.return_value = mock.MagicMock()
        Command.get_course_completions(enterprise_course_enrollments)

    def test_prefetch_users(self):
        """
        Make sure prefetch_users method works as expected.
        """
        # Import is placed here because if placed at the top it affects mocking.
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        user = factories.UserFactory()
        enrollment_grades = {42: mock.Mock(user_id=user.id)}
        expected = {user.id: user}
        assert Command.prefetch_users(enrollment_grades) == expected

    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_completions',
        mock.MagicMock(return_value={1: mock.MagicMock()})
    )
    @mock.patch(
        MODULE_PATH + 'send_course_completion_statement',
        mock.Mock(side_effect=ClientError('EnterpriseXAPIClient request failed.'))
    )
    def test_command_grade_factory(self):
        """
        Make sure NotConnectedToOpenEdX is raised when enterprise app is not installed in Open edX environment.
        """
        # Make sure NotConnectedToOpenEdX is raised if called out side of edx-platform
        xapi_config = factories.XAPILRSConfigurationFactory()
        with raises(
                NotConnectedToOpenEdX,
                match='This package must be installed in an OpenEdX environment.'
        ):
            call_command(
                'send_course_completions',
                enterprise_customer_uuid=xapi_config.enterprise_customer.uuid,
            )

    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'User',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_pertinent_enrollment_ids',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_completions',
        mock.MagicMock(return_value={1: mock.MagicMock()})
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=True)
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_xapi_transmission_queryset',
        mock.MagicMock(return_value=[mock.Mock(
            id=1234,
            enterprise_course_enrollment_id=23243,
            course_id='course-v1:edX+DemoX+Demo_Course'
        )])
    )
    @mock.patch(MODULE_PATH + 'send_course_completion_statement')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_command(self, mock_send_completion_statement, mock_catalog_client):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        xapi_config = factories.XAPILRSConfigurationFactory()
        if mock_catalog_client is not None:
            call_command('send_course_completions', enterprise_customer_uuid=xapi_config.enterprise_customer.uuid)
        assert mock_send_completion_statement.called

    @mock.patch(
        MODULE_PATH + 'User',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_enterprise_course_enrollments',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_enterprise_enrollment_ids',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_xapi_transmission_queryset',
        mock.MagicMock(return_value=[mock.Mock(
            id=1234,
            enterprise_course_enrollment_id=23243,
            course_id='course-v1:edX+DemoX+Demo_Course'
        )])
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_pertinent_enrollment_ids',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_pertinent_enrollments',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_completions',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=True)
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient', mock.MagicMock())
    @mock.patch(MODULE_PATH + 'send_course_completion_statement')
    def test_command_once_for_all_customers(self, mock_send_completion_statement):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        factories.XAPILRSConfigurationFactory.create_batch(5)
        call_command('send_course_completions')
        assert mock_send_completion_statement.call_count == 5

    @mock.patch(
        MODULE_PATH + 'CourseOverview',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_enterprise_course_enrollments',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_enterprise_enrollment_ids',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_xapi_transmission_queryset',
        mock.MagicMock(return_value=[mock.Mock(
            id=1234,
            enterprise_course_enrollment_id=23243,
            course_id='course-v1:edX+DemoX+Demo_Course'
        )])
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_pertinent_enrollment_ids',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_pertinent_enrollments',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_completions',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=False)
    )
    @mock.patch(
        MODULE_PATH + 'send_course_completion_statement',
        mock.MagicMock()
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient', mock.MagicMock())
    def test_command_send_statement_error_response(self):
        factories.XAPILRSConfigurationFactory()
        call_command('send_course_completions')

    def test_get_object_type(self):
        """
        Make sure get_object_type logic works as expected.
        """
        # Import is placed here because if placed at the top it affects mocking.
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        xapi_transmission = mock.Mock(course_id='edX+DemoX')
        assert Command.get_object_type(xapi_transmission) == 'course'

        xapi_transmission = mock.Mock(course_id='course-v1:edX+DemoX+Demo_Course')
        assert Command.get_object_type(xapi_transmission) == 'courserun'

    @mock.patch(MODULE_PATH + 'XAPILearnerDataTransmissionAudit')
    def test_get_xapi_transmission_queryset(self, mock_transmission_audit):
        """
        Make sure operation works as expected.
        """
        # Import is placed here because if placed at the top it affects mocking.
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        enterprise_enrollment_ids = [2, 24, 632]
        Command.get_xapi_transmission_queryset(enterprise_enrollment_ids)
        assert mock_transmission_audit.objects.filter.called

    def test_get_pertinent_enrollment_ids(self):
        """
        Make sure operation works as expected.
        """
        # Import is placed here because if placed at the top it affects mocking.
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        mock_transmission_queryset = mock.MagicMock(return_value=[mock.Mock(
            id=1234,
            enterprise_course_enrollment_id=23243,
            course_id='course-v1:edX+DemoX+Demo_Course'
        )])
        Command.get_pertinent_enrollment_ids(mock_transmission_queryset)

    @mock.patch(
        MODULE_PATH + 'Command.get_grade_record_for_enrollment',
        mock.MagicMock(return_value=None)
    )
    @mock.patch(
        MODULE_PATH + 'PersistentCourseGrade',
        mock.MagicMock()
    )
    # @mock.patch(MODULE_PATH + 'PersistentCourseGrade')
    def test_get_course_completions_no_grade_record(self):
        """
        Make sure get_course_completions works as expected
        """
        from integrated_channels.xapi.management.commands.send_course_completions import Command

        user = factories.UserFactory()
        enterprise_course_enrollments = [
            mock.Mock(id=42, user_id=user.id)
        ]
        Command.get_course_completions(enterprise_course_enrollments)
