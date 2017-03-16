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
from test_utils.fake_catalog_api import get_catalog_courses, get_course_details


@mark.django_db
class TestTransmitCoursewareDataManagementCommand(unittest.TestCase):
    """
    Test the transmit_courseware_data management command.
    """
    def setUp(self):

        self.user = UserFactory(username='C-3PO')
        self.enterprise_customer = EnterpriseCustomerFactory(
            catalog=1,
            name='Veridian Dynamics',
        )
        self.integrated_channel = SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.create(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
            active=True,
        )

        super(TestTransmitCoursewareDataManagementCommand, self).setUp()

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()
        error = 'Enterprise customer {} not found, or not active'.format(invalid_customer_id)
        with raises(CommandError) as excinfo:
            call_command('transmit_courseware_data', '--catalog_user', 'C-3PO', enterprise_customer=invalid_customer_id)
        assert str(excinfo.value) == error

    def test_user_not_set(self):
        # Python2 and Python3 have different error strings. So that's great.
        py2error = 'Error: argument --catalog_user is required'
        py3error = 'Error: the following arguments are required: --catalog_user'
        with raises(CommandError) as excinfo:
            call_command('transmit_courseware_data', enterprise_customer=self.enterprise_customer.uuid)
        assert str(excinfo.value) in (py2error, py3error)

    def test_override_user(self):
        error = 'A user with the username bob was not found.'
        with raises(CommandError) as excinfo:
            call_command('transmit_courseware_data', '--catalog_user', 'bob')
        assert str(excinfo.value) == error

    @mock.patch('integrated_channels.integrated_channel.management.commands.transmit_courseware_data.send_data_task')
    def test_working_user(self, mock_data_task):
        call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')
        mock_data_task.delay.assert_called_once_with('C-3PO', 'SAP', 1)


@mark.django_db
@mock.patch('integrated_channels.integrated_channel.course_metadata.CourseCatalogApiClient')
def test_transmit_courseware_task_success(fake_catalog_client, caplog):
    """
    Test the data transmission task.
    """
    fake_catalog_client.return_value = mock.MagicMock(
        get_course_details=get_course_details,
        get_catalog_courses=get_catalog_courses,
    )

    caplog.set_level(logging.INFO)

    UserFactory(username='C-3PO')
    enterprise_customer = EnterpriseCustomerFactory(
        catalog=1,
        name='Veridian Dynamics',
    )
    SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.create(
        enterprise_customer=enterprise_customer,
        sapsf_base_url='enterprise.successfactors.com',
        key='key',
        secret='secret',
        active=True,
    )

    call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')

    assert len(caplog.records) == 7
    expected_dump = (
        '{"ocnCourses": [{"content": [{"contentID": "course-v1:edX+DemoX+Demo_Course", '
        '"contentTitle": "Course Description", "launchType": 3, "launchURL": "http://l'
        'ocalhost:8000/course/edxdemox?utm_source=admin&utm_medium=affiliate_partner",'
        ' "mobileEnabled": false, "providerID": "EDX"}], "courseID": "course-v1:edX+De'
        'moX+Demo_Course", "description": [{"locale": "English", "value": ""}], "dura'
        'tion": "", "price": [], "providerID": "EDX", "revisionNumber": 1, "schedule"'
        ': [{"active": true, "duration": "", "endDate": 2147483647000, "startDate": 1'
        '360040400000}], "status": "INACTIVE", "thumbnailURI": "http://192.168.1.187:'
        '8000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        '", "title": [{"locale": "English", "value": "edX Demonstration Course"}]}, {'
        '"content": [{"contentID": "course-v1:foobar+fb1+fbv1", "contentTitle": "Cour'
        'se Description", "launchType": 3, "launchURL": "http://localhost:8000/course'
        '/foobarfb1?utm_source=admin&utm_medium=affiliate_partner", "mobileEnabled": '
        'false, "providerID": "EDX"}], "courseID": "course-v1:foobar+fb1+fbv1", "desc'
        'ription": [{"locale": "English", "value": "This is a really cool course. Lik'
        'e, we promise."}], "duration": "", "price": [], "providerID": "EDX", "revisi'
        'onNumber": 1, "schedule": [{"active": true, "duration": "", "endDate": 21474'
        '83647000, "startDate": 1420070400000}], "status": "INACTIVE", "thumbnailURI"'
        ': "http://192.168.1.187:8000/asset-v1:foobar+fb1+fbv1+type@asset+block@image'
        's_course_image.jpg", "title": [{"locale": "English", "value": "Other Course '
        'Name"}]}]}'
    )
    expected_messages = [
        'Processing courses for integrated channel using configuration: '
        '<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>',
        'Retrieving course list for catalog 1',
        'Processing course with ID course-v1:edX+DemoX+Demo_Course',
        'Sending course with plugin configuration <SAPSuccessFactorsEnterprise'
        'CustomerConfiguration for Enterprise Veridian Dynamics>',
        'Processing course with ID course-v1:foobar+fb1+fbv1',
        'Sending course with plugin configuration <SAPSuccessFactorsEnterprise'
        'CustomerConfiguration for Enterprise Veridian Dynamics>',
        expected_dump,
    ]
    for i, msg in enumerate(expected_messages):
        assert msg in caplog.records[i].message


@mark.django_db
@mock.patch('integrated_channels.integrated_channel.course_metadata.CourseCatalogApiClient')
def test_transmit_courseware_task_no_channel(fake_catalog_client, caplog):
    """
    Test the data transmission task.
    """
    fake_catalog_client.return_value = mock.MagicMock(
        get_course_details=get_course_details,
        get_catalog_courses=get_catalog_courses,
    )

    caplog.set_level(logging.INFO)

    UserFactory(username='C-3PO')
    EnterpriseCustomerFactory(
        catalog=1,
        name='Veridian Dynamics',
    )

    call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')

    # Because there are no IntegratedChannels, the process will end early.
    assert len(caplog.records) == 0


@mark.django_db
@mock.patch('integrated_channels.integrated_channel.course_metadata.CourseCatalogApiClient')
def test_transmit_courseware_task_no_catalog(fake_catalog_client, caplog):
    """
    Test the data transmission task.
    """
    fake_catalog_client.return_value = mock.MagicMock(
        get_course_details=get_course_details,
        get_catalog_courses=get_catalog_courses,
    )

    caplog.set_level(logging.INFO)

    UserFactory(username='C-3PO')
    enterprise_customer = EnterpriseCustomerFactory(
        catalog=None,
        name='Veridian Dynamics',
    )
    SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.create(
        enterprise_customer=enterprise_customer,
        sapsf_base_url='enterprise.successfactors.com',
        key='key',
        secret='secret',
        active=True,
    )

    call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')

    # Because there are no EnterpriseCustomers with a catalog, the process will end early.
    assert len(caplog.records) == 0


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
        error = 'Enterprise customer {} not found, or not active'.format(invalid_customer_id)
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
