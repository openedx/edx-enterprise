# -*- coding: utf-8 -*-
"""
Test xAPI management command to send course enrollments data.
"""

from __future__ import absolute_import, unicode_literals

import unittest
import uuid

import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.core.management import CommandError, call_command

from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories

MODULE_PATH = 'integrated_channels.xapi.management.commands.send_course_enrollments.'


@mark.django_db
class TestSendCourseEnrollments(unittest.TestCase):
    """
    Tests for the ``send_course_enrollments`` management command.
    """
    def setUp(self):
        super(TestSendCourseEnrollments, self).setUp()
        faker = FakerFactory.create()

        # pylint: disable=no-member
        self.course_overview = mock.Mock(
            id='course-v1:edX+DemoX+Demo_Course',
            display_name=faker.text(max_nb_chars=25),
            short_description=faker.text(),
            key='edX+DemoX',
        )

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
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
            call_command('send_course_enrollments', days=1, enterprise_customer_uuid=enterprise_uuid)

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
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
            call_command('send_course_enrollments', days=1, enterprise_customer_uuid=enterprise_customer.uuid)

    @mock.patch(
        MODULE_PATH + 'send_course_enrollment_statement',
        mock.MagicMock()
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient', mock.MagicMock())
    def test_get_course_enrollments(self):
        """
        Make sure NotConnectedToOpenEdX is raised when enterprise app is not installed in Open edX environment.
        """
        xapi_config = factories.XAPILRSConfigurationFactory()

        with raises(
                NotConnectedToOpenEdX,
                match='This package must be installed in an OpenEdX environment.'
        ):
            call_command(
                'send_course_enrollments',
                days=1,
                enterprise_customer_uuid=xapi_config.enterprise_customer.uuid,
            )

        # Verify that get_course_enrollments returns CourseEnrollment records
        with mock.patch(
                MODULE_PATH + 'CourseEnrollment'
        ) as mock_enrollments:
            call_command('send_course_enrollments')
            assert mock_enrollments.objects.filter.called

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
        mock.MagicMock()
    )
    # pylint: disable=invalid-name
    @mock.patch(
        MODULE_PATH + 'Command.get_course_enrollments',
        mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'XAPILearnerDataTransmissionAudit.objects.get_or_create',
        mock.MagicMock(return_value=(mock.MagicMock(), True))
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=True)
    )
    @mock.patch(MODULE_PATH + 'send_course_enrollment_statement')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_command(self, mock_send_statement, mock_catalog_client):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        xapi_config = factories.XAPILRSConfigurationFactory()
        if mock_catalog_client is not None:
            call_command('send_course_enrollments', enterprise_customer_uuid=xapi_config.enterprise_customer.uuid)
        assert mock_send_statement.called

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'XAPILearnerDataTransmissionAudit.objects.get_or_create',
        mock.MagicMock(return_value=(mock.MagicMock(), True))
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=True)
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_enrollments',
        mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])
    )
    @mock.patch(MODULE_PATH + 'send_course_enrollment_statement')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_command_once_for_all_customers(self, mock_send_statement, mock_catalog_client):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        factories.XAPILRSConfigurationFactory.create_batch(5)
        if mock_catalog_client is not None:
            call_command('send_course_enrollments')
        assert mock_send_statement.call_count == 5

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'is_success_response',
        mock.MagicMock(return_value=False)
    )
    @mock.patch(
        MODULE_PATH + 'send_course_enrollment_statement',
        mock.MagicMock(return_value={'status': 500, 'error_message': 'Darn'})
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_enrollments',
        mock.MagicMock(return_value=[mock.MagicMock(user_id=1234), mock.MagicMock(user_id=2468)])
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient', mock.MagicMock())
    def test_command_send_statement_error_response(self):
        factories.XAPILRSConfigurationFactory()
        call_command('send_course_enrollments')

    def test_save_xapi_learner_data_transmission_audit(self):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        Command.save_xapi_learner_data_transmission_audit(
            factories.UserFactory(),
            'course-v1:edX+DemoX+Demo_Course',
            42,
            status=200,
            error_message=None
        )

    @mock.patch(MODULE_PATH + 'XAPILearnerDataTransmissionAudit')
    def test_save_xapi_learner_data_transmission_audit_preexisting(self, mock_transmission_audit):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        mock_transmission_audit.objects.get_or_create.return_value = (mock.MagicMock(), False)
        Command.save_xapi_learner_data_transmission_audit(
            factories.UserFactory(),
            'course-v1:edX+DemoX+Demo_Course',
            42,
            status=200,
            error_message=None
        )

    @mock.patch(
        MODULE_PATH + 'Command.is_already_transmitted',
        mock.MagicMock(return_value=False)
    )
    def test_get_pertinent_course_enrollments(self):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        course_id = 'course-v1:edX+DemoX+Demo_Course'
        xapi_transmissions = mock.MagicMock()

        course_enrollments = [
            mock.Mock(user_id=12, course_id=course_id),
            mock.Mock(user_id=23, course_id=course_id),
            mock.Mock(user_id=34, course_id=course_id),
            mock.Mock(user_id=45, course_id=course_id),
        ]

        response = Command.get_pertinent_course_enrollments(
            course_enrollments,
            xapi_transmissions
        )
        assert len(response) == 4

    @mock.patch(
        MODULE_PATH + 'Command.is_already_transmitted',
        mock.MagicMock(return_value=True)
    )
    def test_get_pertinent_course_enrollments_already_transmitted(self):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        course_id = 'course-v1:edX+DemoX+Demo_Course'
        xapi_transmissions = mock.MagicMock()

        course_enrollments = [
            mock.Mock(user_id=12, course_id=course_id),
            mock.Mock(user_id=23, course_id=course_id),
            mock.Mock(user_id=34, course_id=course_id),
            mock.Mock(user_id=45, course_id=course_id),
        ]

        response = Command.get_pertinent_course_enrollments(
            course_enrollments,
            xapi_transmissions
        )
        assert len(response) == 0

    def test_get_pertinent_course_enrollments_no_enrollments(self):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        course_id = 'course-v1:edX+DemoX+Demo_Course'
        xapi_transmissions = mock.MagicMock()
        xapi_transmissions.filter.return_value = [
            mock.MagicMock(user_id=12, course_id=course_id),
            mock.MagicMock(user_id=23, course_id=course_id)
        ]

        course_enrollments = []

        response = Command.get_pertinent_course_enrollments(
            course_enrollments,
            xapi_transmissions
        )
        assert len(response) == 0

    def test_is_already_transmitted(self):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        user_id = 12
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        xapi_transmissions = mock.MagicMock()
        xapi_transmissions.filter.return_value = [
            mock.MagicMock(user_id=user_id, course_id=course_id)
        ]

        Command.is_already_transmitted(xapi_transmissions, user_id, course_id)

    @mock.patch(
        'integrated_channels.xapi.utils.is_success_response',
        mock.MagicMock(return_value=False)
    )
    @mock.patch(MODULE_PATH + 'send_course_enrollment_statement')
    def test_transmit_course_enrollments_transmit_fail_skip(self, mock_send_statement):
        from integrated_channels.xapi.management.commands.send_course_enrollments import Command

        lrs_configuration = factories.XAPILRSConfigurationFactory()
        user = factories.UserFactory()
        course = self.course_overview

        Command.transmit_courserun_enrollment_statement(lrs_configuration, user, course)
        assert mock_send_statement.called
