# -*- coding: utf-8 -*-
"""
Test xAPI management command to send course enrollments data.
"""

from __future__ import absolute_import, unicode_literals

import logging
import unittest
import uuid

import mock
from pytest import mark, raises

from django.core.management import CommandError, call_command

from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.exceptions import ClientError
from test_utils import MockLoggingHandler, factories

MODULE_PATH = 'integrated_channels.xapi.management.commands.send_course_enrollments.'


@mark.django_db
class TestSendCourseEnrollments(unittest.TestCase):
    """
    Tests for the ``send_course_enrollments`` management command.
    """

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
        mock.MagicMock(return_value=[mock.MagicMock()])
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'XAPILearnerDataTransmissionAudit.objects.get_or_create',
        mock.MagicMock(return_value=(mock.MagicMock(), True))
    )
    @mock.patch(MODULE_PATH + 'send_course_enrollment_statement')
    def test_command(self, mock_send_course_enrollment_statement):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        xapi_config = factories.XAPILRSConfigurationFactory()
        call_command('send_course_enrollments', enterprise_customer_uuid=xapi_config.enterprise_customer.uuid)

        assert mock_send_course_enrollment_statement.called

    @mock.patch(
        MODULE_PATH + 'CourseEnrollment',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'XAPILearnerDataTransmissionAudit.objects.get_or_create',
        mock.MagicMock(return_value=(mock.MagicMock(), True))
    )
    @mock.patch(
        MODULE_PATH + 'Command.get_course_enrollments',
        mock.MagicMock(return_value=[mock.MagicMock()])
    )
    @mock.patch(
        MODULE_PATH + 'EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id',
        mock.MagicMock()
    )
    @mock.patch(
        MODULE_PATH + 'send_course_enrollment_statement',
        mock.Mock(side_effect=ClientError('EnterpriseXAPIClient request failed.'))
    )
    def test_command_client_error(self):
        """
        Make command handles networking issues gracefully.
        """
        logger = logging.getLogger('integrated_channels.xapi.management.commands.send_course_enrollments')
        handler = MockLoggingHandler(level="DEBUG")
        logger.addHandler(handler)

        xapi_config = factories.XAPILRSConfigurationFactory()
        call_command('send_course_enrollments', enterprise_customer_uuid=xapi_config.enterprise_customer.uuid)
        expected_message = (
            'Client error while sending course enrollment to xAPI for enterprise '
            'customer: {enterprise_customer}'.format(enterprise_customer=xapi_config.enterprise_customer.name)
        )

        assert expected_message in handler.messages['error'][0]

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
    # pylint: disable=invalid-name
    @mock.patch(
        MODULE_PATH + 'Command.get_course_enrollments',
        mock.MagicMock(return_value=[mock.MagicMock()])
    )
    @mock.patch(MODULE_PATH + 'send_course_enrollment_statement')
    def test_command_once_for_all_customers(self, mock_send_course_enrollment_statement):
        """
        Make command runs successfully and sends correct data to the LRS.
        """
        factories.XAPILRSConfigurationFactory.create_batch(5)
        call_command('send_course_enrollments')

        assert mock_send_course_enrollment_statement.call_count == 5
