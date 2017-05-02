"""
Test the Enterprise management commands and related functions.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import logging
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta

import mock
import responses
from faker import Factory as FakerFactory
from freezegun import freeze_time
from integrated_channels.integrated_channel.learner_data import BaseLearnerExporter
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from pytest import mark, raises
from requests.compat import urljoin

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from enterprise import lms_api
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
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
            sapsf_base_url='http://enterprise.successfactors.com/',
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
@mock.patch('integrated_channels.sap_success_factors.utils.reverse')
@mock.patch('integrated_channels.integrated_channel.course_metadata.CourseCatalogApiClient')
@mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
def test_transmit_courseware_task_success(fake_client, fake_catalog_client, track_selection_reverse_mock, caplog):
    """
    Test the data transmission task.
    """
    fake_client.get_oauth_access_token.return_value = "token", datetime.utcnow()
    fake_client.return_value.send_course_import.return_value = 200, '{}'

    fake_catalog_client.return_value = mock.MagicMock(
        get_course_details=get_course_details,
        get_catalog_courses=get_catalog_courses,
    )

    track_selection_reverse_mock.return_value = '/course_modes/choose/course-v1:edX+DemoX+Demo_Course/'

    caplog.set_level(logging.INFO)

    UserFactory(username='C-3PO')
    enterprise_customer = EnterpriseCustomerFactory(
        catalog=1,
        name='Veridian Dynamics',
        site__domain='example.com'
    )
    SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.create(
        enterprise_customer=enterprise_customer,
        sapsf_base_url='http://enterprise.successfactors.com/',
        key='key',
        secret='secret',
        active=True,
    )

    call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')

    fake_client.return_value.send_course_import.assert_called()
    assert len(caplog.records) == 7
    expected_dump = (
        '{"ocnCourses": [{"content": [{"contentID": "course-v1:edX+DemoX+Demo_Course", '
        '"contentTitle": "edX Demonstration Course", "launchType": 3, "launchURL": "htt'
        'ps://example.com/course_modes/choose/course-v1:edX+DemoX+Demo_Course/",'
        ' "mobileEnabled": false, "providerID": "EDX"}], "courseID": "course-v1:edX+De'
        'moX+Demo_Course", "description": [{"locale": "English", "value": "edX Demonst'
        'ration Course"}], "price": [], "providerID": "EDX", "revisionNumber": 1, "sch'
        'edule": [{"active": true, "endDate": 2147483647000, "startDate": 136004040000'
        '0}], "status": "ACTIVE", "thumbnailURI": "http://192.168.1.187:8000/asset-v1:'
        'edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg", "title": [{"'
        'locale": "English", "value": "edX Demonstration Course"}]}, {"content": [{"co'
        'ntentID": "course-v1:foobar+fb1+fbv1", "contentTitle": "Other Course Name", "'
        'launchType": 3, "launchURL": "https://example.com/course_modes/choose/course-'
        'v1:edX+DemoX+Demo_Course/", "mobileEnabled": false, "providerID": "EDX"}], "c'
        'ourseID": "course-v1:foobar+fb1+fbv1", "description": [{"locale": "English", '
        '"value": "This is a really cool course. Like, we promise."}], "price": [], "p'
        'roviderID": "EDX", "revisionNumber": 1, "schedule": [{"active": true, "endDat'
        'e": 2147483647000, "startDate": 1420070400000}], "status": "ACTIVE", "thumbna'
        'ilURI": "http://192.168.1.187:8000/asset-v1:foobar+fb1+fbv1+type@asset+block@'
        'images_course_image.jpg", "title": [{"locale": "English", "value": "Other Cou'
        'rse Name"}]}]}'
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
        sapsf_base_url='http://enterprise.successfactors.com/',
        key='key',
        secret='secret',
        active=True,
    )

    call_command('transmit_courseware_data', '--catalog_user', 'C-3PO')

    # Because there are no EnterpriseCustomers with a catalog, the process will end early.
    assert len(caplog.records) == 0


# Constants used in the parameters for the transmit_learner_data integration tests below.
NOW = datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP = 1483326245000
DAY_DELTA = timedelta(days=1)
PAST = NOW - DAY_DELTA
PAST_TIMESTAMP = NOW_TIMESTAMP - 24*60*60*1000
FUTURE = NOW + DAY_DELTA

COURSE_ID = 'course-v1:edX+DemoX+DemoCourse'

# Mock passing certificate data
MOCK_PASSING_CERTIFICATE = dict(
    grade='A-',
    created_date=NOW.strftime(lms_api.LMS_API_DATETIME_FORMAT),
    status='downloadable',
    is_passing=True,
)

# Mock failing certificate data
MOCK_FAILING_CERTIFICATE = dict(
    grade='D',
    created_date=NOW.strftime(lms_api.LMS_API_DATETIME_FORMAT),
    status='downloadable',
    is_passing=False,
)

# Expected learner completion data from the mock passing certificate
CERTIFICATE_PASSING_COMPLETION = dict(
    completed='true',
    timestamp=NOW_TIMESTAMP,
    grade=BaseLearnerExporter.GRADE_PASSING,
)

# Expected learner completion data from the mock failing certificate
CERTIFICATE_FAILING_COMPLETION = dict(
    completed='false',
    timestamp=NOW_TIMESTAMP,
    grade=BaseLearnerExporter.GRADE_FAILING,
)


@mark.django_db
class TestTransmitLearnerData(unittest.TestCase):
    """
    Test the transmit_learner_data management command.
    """
    def setUp(self):
        self.api_user = UserFactory(username='staff_user')
        self.user = UserFactory()
        self.course_id = COURSE_ID
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.identity_provider = FakerFactory.create().slug()
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.identity_provider,
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

    def test_api_user_required(self):
        error = 'Error: argument --api_user is required'
        with raises(CommandError, message=error):
            call_command('transmit_learner_data')

    def test_api_user_must_exist(self):
        error = 'A user with the username bob was not found.'
        with raises(CommandError, message=error):
            call_command('transmit_learner_data', '--api_user', 'bob')

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()
        error = 'Enterprise customer {} not found, or not active'.format(invalid_customer_id)
        with raises(CommandError, message=error):
            call_command('transmit_learner_data',
                         '--api_user', self.api_user.username,
                         enterprise_customer=invalid_customer_id)

    def test_invalid_integrated_channel(self):
        channel_code = 'abc'
        error = 'Invalid integrated channel: {}'.format(channel_code)
        with raises(CommandError, message=error):
            call_command('transmit_learner_data',
                         '--api_user', self.api_user.username,
                         enterprise_customer=self.enterprise_customer.uuid,
                         channel=channel_code)


# Helper methods used for the transmit_learner_data integration tests below.
@contextmanager
def transmit_learner_data_context(command_kwargs, certificate, self_paced, end_date, passed):
    """
    Sets up all the data and context wrappers required to run the transmit_learner_data management command.
    """
    # Borrow the test data from TestTransmitLearnerData
    testcase = TestTransmitLearnerData(methodName='setUp')
    testcase.setUp()

    # Activate the integrated channel
    testcase.integrated_channel.active = True
    testcase.integrated_channel.save()

    # Stub out the APIs called by the transmit_learner_data command
    stub_transmit_learner_data_apis(testcase, certificate, self_paced, end_date, passed)

    # Prepare the management command arguments
    command_args = ('--api_user', testcase.api_user.username)
    if 'enterprise_customer' in command_kwargs:
        command_kwargs['enterprise_customer'] = testcase.enterprise_customer.uuid

    # Mock the JWT authentication for LMS API calls
    with mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock()):

        # Yield to the management command test, freezing time to the known NOW.
        with freeze_time(NOW):
            yield (command_args, command_kwargs)

    # Clean up the testcase data
    testcase.tearDown()


# Helper methods for the transmit_learner_data integration test below
def stub_transmit_learner_data_apis(testcase, certificate, self_paced, end_date, passed):
    """
    Stub out all of the API calls made during transmit_learner_data
    """

    # Third Party API remote_id response
    responses.add(
        responses.GET,
        urljoin(lms_api.ThirdPartyAuthApiClient.API_BASE_URL,
                "providers/{provider}/users/{user}".format(provider=testcase.identity_provider,
                                                           user=testcase.user.username)),
        json=dict(results=[
            dict(username=testcase.user.username, remote_id='remote-user-id'),
        ]),
    )

    # Course API course_details response
    responses.add(
        responses.GET,
        urljoin(lms_api.CourseApiClient.API_BASE_URL,
                "courses/{course}/".format(course=testcase.course_id)),
        json=dict(
            course_id=COURSE_ID,
            pacing="self" if self_paced else "instructor",
            end=end_date.isoformat() if end_date else None,
        ),
    )

    # Grades API course_grades response
    responses.add(
        responses.GET,
        urljoin(lms_api.GradesApiClient.API_BASE_URL,
                "course_grade/{course}/users/?username={user}".format(course=testcase.course_id,
                                                                      user=testcase.user.username)),
        match_querystring=True,
        json=[dict(
            username=testcase.user.username,
            course_id=COURSE_ID,
            passed=passed,
        )],
    )

    # Certificates API course_grades response
    if certificate:
        responses.add(
            responses.GET,
            urljoin(lms_api.CertificatesApiClient.API_BASE_URL,
                    "certificates/{user}/courses/{course}/".format(course=testcase.course_id,
                                                                   user=testcase.user.username)),
            json=certificate,
        )
    else:
        responses.add(
            responses.GET,
            urljoin(lms_api.CertificatesApiClient.API_BASE_URL,
                    "certificates/{user}/courses/{course}/".format(course=testcase.course_id,
                                                                   user=testcase.user.username)),
            status=404,
        )


def get_expected_output(**expected_completion):
    """
    Returns the expected JSON record logged by the transmit_learner_data command.
    """
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
    return output_template.format(
        user_id='remote-user-id',
        course_id=COURSE_ID,
        provider_id="EDX",
        **expected_completion
    )


@responses.activate
@mark.django_db
@mark.parametrize('command_kwargs,certificate,self_paced,end_date,passed,expected_completion', [
    # Certificate marks course completion
    (dict(), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
    (dict(), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),
    # channel code is case-insensitive
    (dict(channel='sap'), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
    (dict(channel='SAP'), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
    (dict(channel='sap'), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),
    (dict(channel='SAP'), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),
    # enterprise_customer UUID gets filled in below
    (dict(enterprise_customer=None), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
    (dict(enterprise_customer=None, channel='sap'), MOCK_PASSING_CERTIFICATE, False, None, False,
     CERTIFICATE_PASSING_COMPLETION),
    (dict(enterprise_customer=None), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),
    (dict(enterprise_customer=None, channel='sap'), MOCK_FAILING_CERTIFICATE, False, None, False,
     CERTIFICATE_FAILING_COMPLETION),

    # Instructor-paced course with no certificates issued yet results in incomplete course data
    (dict(), None, False, None, False, dict(completed='false', timestamp='null', grade='In Progress')),

    # Self-paced course with no end date send grade=Pass, or grade=In Progress, depending on current grade.
    (dict(), None, True, None, False, dict(completed='false', timestamp='null', grade='In Progress')),
    (dict(), None, True, None, True, dict(completed='true', timestamp=NOW_TIMESTAMP, grade='Pass')),

    # Self-paced course with future end date sends grade=Pass, or grade=In Progress, depending on current grade.
    (dict(), None, True, FUTURE, False, dict(completed='false', timestamp='null', grade='In Progress')),
    (dict(), None, True, FUTURE, True, dict(completed='true', timestamp=NOW_TIMESTAMP, grade='Pass')),

    # Self-paced course with past end date sends grade=Pass, or grade=Fail, depending on current grade.
    (dict(), None, True, PAST, False, dict(completed='false', timestamp=PAST_TIMESTAMP, grade='Fail')),
    (dict(), None, True, PAST, True, dict(completed='true', timestamp=PAST_TIMESTAMP, grade='Pass')),
])
def test_transmit_learner_data(caplog, command_kwargs, certificate, self_paced, end_date, passed, expected_completion):
    """
    Test the log output from a successful run of the transmit_learner_data management command,
    using all the ways we can invoke it.
    """
    caplog.set_level(logging.INFO)

    # Mock the Open edX environment classes
    with transmit_learner_data_context(command_kwargs, certificate, self_paced, end_date, passed) as (args, kwargs):
        with mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient') \
                as mock_client:
            mock_client.get_oauth_access_token.return_value = "token", datetime.utcnow()
            mock_client.return_value.send_completion_status.return_value = 200, '{}'
            # Call the management command
            call_command('transmit_learner_data', *args, **kwargs)

    # Ensure the correct learner_data record was logged
    assert len(caplog.records) == 1

    expected_output = get_expected_output(**expected_completion)
    assert expected_output in caplog.records[0].message
