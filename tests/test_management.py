"""
Test the Enterprise management commands and related functions.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import logging
import unittest
from datetime import datetime

import mock
from faker import Factory as FakerFactory
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from pytest import mark, raises

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from test_utils.factories import (EnterpriseCourseEnrollmentFactory, EnterpriseCustomerFactory,
                                  EnterpriseCustomerIdentityProviderFactory, EnterpriseCustomerUserFactory,
                                  UserFactory)


@mark.django_db
class TestTransmitLearnerData(unittest.TestCase):
    """
    Test the transmit_learner_data management command.
    """
    def setUp(self):
        self.user = UserFactory(username='R2D2')
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer = EnterpriseCustomerFactory()
        EnterpriseCustomerIdentityProviderFactory(provider_id=FakerFactory.create().slug(),
                                                  enterprise_customer=self.enterprise_customer)
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )
        self.integrated_channel = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
        )

        super(TestTransmitLearnerData, self).setUp()

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()
        error = 'Enterprise customer {} not found, or not active.'.format(invalid_customer_id)
        with raises(CommandError, message=error):
            call_command('transmit_learner_data', enterprise_customer=invalid_customer_id)

    def test_invalid_integrated_channel(self):
        channel_code = 'abc'
        error = 'Invalid integrated channel: {}'.format(channel_code)
        with raises(CommandError, message=error):
            call_command('transmit_learner_data',
                         enterprise_customer=self.enterprise_customer.uuid,
                         channel=channel_code)


@mark.django_db
@mark.parametrize('command_args', [
    dict(),
    dict(channel='sap'),  # channel code is case-insensitive
    dict(channel='SAP'),
    dict(enterprise_customer=None),  # enterprise_customer UUID gets filled in below
    dict(enterprise_customer=None, channel='sap'),
])
def test_transmit_learner_data(caplog, command_args):
    """
    Test the log output from a successful run of the transmit_learner_data management command,
    using all the ways we can invoke it.
    """
    caplog.set_level(logging.INFO)

    # Borrow the test data from TestTransmitLearnerData
    testcase = TestTransmitLearnerData(methodName='setUp')
    testcase.setUp()

    # Activate the integrated channel
    testcase.integrated_channel.active = True
    testcase.integrated_channel.save()

    # Expect the learner data record to be sent to the logger
    output_template = (
        '{{'
        '"comments": "", '
        '"completedTimestamp": {timestamp}, '
        '"contactHours": "", '
        '"courseCompleted": "{completed}", '
        '"courseID": "{course_id}", '
        '"cpeHours": "", '
        '"creditHours": "", '
        '"currency": "", '
        '"grade": "{grade}", '
        '"instructorName": "", '
        '"price": "", '
        '"providerID": "{provider_id}", '
        '"totalHours": "", '
        '"userID": "{user_id}"'
        '}}'
    )
    expected_output = output_template.format(
        user_id='remote-r2d2',
        course_id=testcase.course_id,
        provider_id="EDX",
        completed="true",
        timestamp=1483326245,
        grade="A-",
    )

    # Populate the command arguments
    if 'enterprise_customer' in command_args:
        command_args['enterprise_customer'] = testcase.enterprise_customer.uuid

    with mock.patch('enterprise.models.ThirdPartyAuthApiClient') as mock_third_party_api:
        mock_third_party_api.return_value.get_remote_id.return_value = 'remote-r2d2'

        with mock.patch('integrated_channels.integrated_channel.models.CourseKey') as mock_course_key:
            mock_course_key.from_string.return_value = None

            with mock.patch('integrated_channels.integrated_channel.models.GeneratedCertificate') as mock_certificate:
                # Mark course completion with a mock certificate.
                mock_certificate.eligible_certificates.get.return_value = mock.MagicMock(
                    user=testcase.user,
                    course_id=testcase.course_id,
                    grade="A-",
                    created_date=datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
                    status="downloadable",
                )

                # Call the management command
                call_command('transmit_learner_data', **command_args)

    # Ensure the correct learner_data record was logged
    assert len(caplog.records) == 1
    assert expected_output in caplog.records[0].message

    # Clean up the testcase data
    testcase.tearDown()
