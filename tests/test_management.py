"""
Test the Enterprise management commands and related functions.
"""

import logging
import random
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock, skip

import ddt
import factory
import pytz
import responses
from faker import Factory as FakerFactory
from freezegun import freeze_time
from pytest import mark, raises
from requests.compat import urljoin
from requests.utils import quote
from testfixtures import LogCapture

from django.contrib import auth
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import signals
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from enterprise import roles_api
from enterprise.api_client import lms as lms_api
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    LMS_API_DATETIME_FORMAT,
)
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.management.commands import (
    ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES,
    CONTENT_METADATA_JOB_INTEGRATED_CHANNEL_CHOICES,
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandMixin,
)
from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    IntegratedChannelAPIRequestLogs,
    OrphanedContentTransmissions,
)
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.sap_success_factors.exporters.learner_data import SapSuccessFactorsLearnerManger
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import ReturnValueSpy, factories
from test_utils.fake_catalog_api import (
    FAKE_COURSE_TO_CREATE,
    FAKE_COURSE_TO_CREATE_2,
    CourseDiscoveryApiTestMixin,
    setup_course_catalog_api_client_mock,
)
from test_utils.fake_enterprise_api import EnterpriseMockMixin

User = auth.get_user_model()
NOW = datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP = 1483326245000
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')
DAY_DELTA = timedelta(days=1)
PAST = NOW - DAY_DELTA
PAST_TIMESTAMP = NOW_TIMESTAMP - 24 * 60 * 60 * 1000
PAST_TIMESTAMP_FORMATTED = PAST.strftime('%F')
FUTURE = NOW + DAY_DELTA

# Silence noisy logs
LOG_OVERRIDES = [
    ('stevedore.extension', logging.ERROR),
]

for log_name, log_level in LOG_OVERRIDES:
    logging.getLogger(log_name).setLevel(log_level)


@ddt.ddt
class TestIntegratedChannelCommandMixin(unittest.TestCase):
    """
    Tests for the ``IntegratedChannelCommandMixin`` class.
    """

    @ddt.data('SAP', 'DEGREED2')
    def test_transmit_content_metadata_specific_channel(self, channel_code):
        """
        Only the channel we input is what we get out.
        """
        channel_class = INTEGRATED_CHANNEL_CHOICES[channel_code]
        assert IntegratedChannelCommandMixin.get_channel_classes(channel_code) == [channel_class]

    def test_does_not_return_unsupported_channels(self):
        """
        If an unsupported channel is requested while retrieving supported channels, should expect an exception.
        """
        channel = (set(INTEGRATED_CHANNEL_CHOICES) - set(ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES)).pop()
        with raises(CommandError) as excinfo:
            IntegratedChannelCommandMixin.get_channel_classes(
                channel,
                assessment_level_support=True,
            )
        assert excinfo.value.args == ('Invalid integrated channel: {channel}'.format(channel=channel),)

    def test_get_assessment_level_reporting_supported_channels(self):
        """
        Only retrieve channels that support assessment level reporting.
        """
        channel = set(ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES).pop()
        channel_class = ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES[channel]
        assert IntegratedChannelCommandMixin.get_channel_classes(
            channel,
            assessment_level_support=True,
        ) == [channel_class]

    def test_get_content_metadata_transmission_job_supported_channels(self):
        """
        Only retrieve channels that support the scheduled content metadata job.
        """
        channel = set(CONTENT_METADATA_JOB_INTEGRATED_CHANNEL_CHOICES).pop()
        channel_class = CONTENT_METADATA_JOB_INTEGRATED_CHANNEL_CHOICES[channel]
        assert IntegratedChannelCommandMixin.get_channel_classes(
            channel,
            content_metadata_job_support=True,
        ) == [channel_class]


@mark.django_db
@ddt.ddt
class TestTransmitCourseMetadataManagementCommand(unittest.TestCase, EnterpriseMockMixin, CourseDiscoveryApiTestMixin):
    """
    Test the ``transmit_content_metadata`` management command.
    """
    # pylint: disable=line-too-long

    def setUp(self):
        self.user = factories.UserFactory(username='C-3PO')
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Veridian Dynamics',
        )
        self.degreed2 = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            degreed_base_url='http://betatest.degreed.com/',
        )
        self.sapsf = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )
        self.sapsf_global_configuration = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.catalog_api_client_mock = self._make_patch(
            self._make_catalog_api_location("CourseCatalogApiServiceClient")
        )
        super().setUp()

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()  # pylint: disable=no-member
        error = 'Enterprise customer {} not found, or not active'.format(invalid_customer_id)
        with raises(CommandError) as excinfo:
            call_command(
                'transmit_content_metadata',
                '--catalog_user',
                'C-3PO',
                enterprise_customer=invalid_customer_id
            )
        assert str(excinfo.value) == error

    def test_user_not_set(self):
        # Python2 and Python3 have different error strings. So that's great.
        py2error = 'Error: argument --catalog_user is required'
        py3error = 'Error: the following arguments are required: --catalog_user'
        with raises(CommandError) as excinfo:
            call_command('transmit_content_metadata', enterprise_customer=self.enterprise_customer.uuid)
        assert str(excinfo.value) in (py2error, py3error)

    def test_override_user(self):
        error = 'A user with the username bob was not found.'
        with raises(CommandError) as excinfo:
            call_command('transmit_content_metadata', '--catalog_user', 'bob')
        assert str(excinfo.value) == error

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.create_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.integrated_channel.management.commands.transmit_content_metadata.transmit_content_metadata.delay')
    def test_transmit_content_metadata_task_with_error(
            self,
            transmit_content_metadata_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
            degreed2_create_content_metadata_mock,
    ):
        """
        Verify the data transmission task for integrated channels with error.

        Test that the management command `transmit_content_metadata` transmits
        courses metadata related to other integrated channels even if an
        integrated channel fails to transmit due to some error.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'
        degreed2_create_content_metadata_mock.return_value = 200, '{}'

        content_filter = {
            'key': ['course-v1:edX+DemoX+Demo_Course_1']
        }
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
            content_filter=content_filter
        )

        # Mock first integrated channel with failure
        enterprise_uuid_for_failure = enterprise_catalog.uuid
        self.mock_enterprise_catalogs_with_error(enterprise_uuid=enterprise_uuid_for_failure)

        # Now create a new integrated channel with a new enterprise and mock
        # enterprise courses API to send failure response
        dummy_enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Dummy Enterprise',
        )
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=dummy_enterprise_customer,
            content_filter=content_filter
        )
        self.mock_enterprise_customer_catalogs(str(enterprise_catalog.uuid))
        dummy_degreed2 = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=dummy_enterprise_customer,
            degreed_base_url='http://betatest.degreed.com/',
            active=True,
        )
        dummy_sapsf = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=dummy_enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )

        expected_calls = [
            mock.call(username='C-3PO', channel_code='SAP', channel_pk=1),
            mock.call(username='C-3PO', channel_code='DEGREED2', channel_pk=1),
        ]

        call_command('transmit_content_metadata', '--catalog_user', 'C-3PO')

        transmit_content_metadata_mock.assert_has_calls(expected_calls, any_order=True)

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.create_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.integrated_channel.management.commands.transmit_content_metadata.transmit_content_metadata.delay')
    def test_transmit_content_metadata_task_success(
            self,
            transmit_content_metadata_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
            degreed2_create_content_metadata_mock,
    ):
        """
        Test the data transmission task.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'
        degreed2_create_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        expected_calls = [
            mock.call(username='C-3PO', channel_code='SAP', channel_pk=1),
            mock.call(username='C-3PO', channel_code='DEGREED2', channel_pk=1),
        ]

        call_command('transmit_content_metadata', '--catalog_user', 'C-3PO')

        transmit_content_metadata_mock.assert_has_calls(expected_calls, any_order=True)

    @responses.activate
    def test_transmit_content_metadata_task_no_channel(self):
        """
        Test the data transmission task without any integrated channel.
        """
        user = factories.UserFactory(username='john_doe')
        factories.EnterpriseCustomerFactory(
            name='Veridian Dynamics',
        )

        # Remove all integrated channels
        SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.all().delete()
        Degreed2EnterpriseCustomerConfiguration.objects.all().delete()

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('transmit_content_metadata', '--catalog_user', user.username)

            # Because there are no IntegratedChannels, the process will end early.
            assert not log_capture.records

    @responses.activate
    def test_transmit_content_metadata_task_inactive_customer(self):
        """
        Test the data transmission task with a channel for an inactive customer
        """
        integrated_channel_enterprise = self.enterprise_customer
        integrated_channel_enterprise.active = False
        integrated_channel_enterprise.save()

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('transmit_content_metadata', '--catalog_user', self.user.username)

            # Because there are no active customers, the process will end early.
            assert not log_capture.records
    # pylint: enable=line-too-long


COURSE_ID = 'course-v1:edX+DemoX+DemoCourse'
COURSE_KEY = 'edX+DemoX'

# Mock passing certificate data
MOCK_PASSING_CERTIFICATE = {
    'grade': 'A-',
    'created_date': NOW.strftime(LMS_API_DATETIME_FORMAT),
    'status': 'downloadable',
    'is_passing': True,
}

# Mock failing certificate data
MOCK_FAILING_CERTIFICATE = {
    'grade': 'D',
    'created_date': NOW.strftime(LMS_API_DATETIME_FORMAT),
    'status': 'downloadable',
    'is_passing': False,
    'percent_grade': 0.6,
}

# Expected learner completion data from the mock passing certificate
CERTIFICATE_PASSING_COMPLETION = {
    'completed': 'true',
    'timestamp': NOW_TIMESTAMP,
    'grade': LearnerExporter.GRADE_PASSING,
    'total_hours': 0.0,
    'percent_grade': 0.8,
}

# Expected learner completion data from the mock failing certificate
CERTIFICATE_FAILING_COMPLETION = {
    'completed': 'false',
    'timestamp': NOW_TIMESTAMP,
    'grade': LearnerExporter.GRADE_FAILING,
    'total_hours': 0.0,
}


@mark.django_db
class TestTransmitLearnerData(unittest.TestCase):
    """
    Test the transmit_learner_data management command.
    """

    def setUp(self):
        self.api_user = factories.UserFactory(username='staff_user', id=1)
        self.user1 = factories.UserFactory(id=2, email='example@email.com')
        self.user2 = factories.UserFactory(id=3, email='example2@email.com')
        self.course_id = COURSE_ID
        self.enterprise_customer = factories.EnterpriseCustomerFactory(name='Spaghetti Enterprise')
        self.identity_provider = FakerFactory.create().slug()  # pylint: disable=no-member
        factories.EnterpriseCustomerIdentityProviderFactory(
            provider_id=self.identity_provider,
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_customer_user1 = factories.EnterpriseCustomerUserFactory(
            user_id=self.user1.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_customer_user2 = factories.EnterpriseCustomerUserFactory(
            user_id=self.user2.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=2,
            enterprise_customer_user=self.enterprise_customer_user1,
            course_id=self.course_id,
        )
        self.enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=3,
            enterprise_customer_user=self.enterprise_customer_user2,
            course_id=self.course_id,
        )
        self.consent1 = factories.DataSharingConsentFactory(
            username=self.user1.username,
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
        )
        self.consent2 = factories.DataSharingConsentFactory(
            username=self.user2.username,
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
        )
        self.degreed = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            key='key',
            secret='secret',
            degreed_company_id='Degreed Company',
            active=True,
            degreed_base_url='https://www.degreed.com/',
        )
        self.degreed_global_configuration = factories.DegreedGlobalConfigurationFactory(
            oauth_api_path='oauth/token',
        )
        self.sapsf = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )
        self.sapsf_global_configuration = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        super().setUp()

    def test_api_user_required(self):
        error = 'Error: the following arguments are required: --api_user'
        with raises(CommandError, match=error):
            call_command('transmit_learner_data')

    def test_api_user_must_exist(self):
        error = 'A user with the username bob was not found.'
        with raises(CommandError, match=error):
            call_command('transmit_learner_data', '--api_user', 'bob')

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()  # pylint: disable=no-member
        error = 'Enterprise customer {} not found, or not active'.format(invalid_customer_id)
        with raises(CommandError, match=error):
            call_command('transmit_learner_data',
                         '--api_user', self.api_user.username,
                         enterprise_customer=invalid_customer_id)

    def test_invalid_integrated_channel(self):
        channel_code = 'ABC'
        error = 'Invalid integrated channel: {}'.format(channel_code)
        with raises(CommandError, match=error):
            call_command('transmit_learner_data',
                         '--api_user', self.api_user.username,
                         enterprise_customer=self.enterprise_customer.uuid,
                         channel=channel_code)


# Helper methods used for the transmit_learner_data integration tests below.
@contextmanager
def transmit_learner_data_context(command_kwargs=None, certificate=None, self_paced=False, end_date=None, passed=False):
    """
    Sets up all the data and context wrappers required to run the transmit_learner_data management command.
    """
    if command_kwargs is None:
        command_kwargs = {}

    # Borrow the test data from TestTransmitLearnerData
    testcase = TestTransmitLearnerData(methodName='setUp')
    testcase.setUp()

    # Stub out the APIs called by the transmit_learner_data command
    stub_transmit_learner_data_apis(testcase, certificate, self_paced, end_date, passed)

    # Prepare the management command arguments
    command_args = ('--api_user', testcase.api_user.username)
    if 'enterprise_customer' in command_kwargs:
        command_kwargs['enterprise_customer'] = testcase.enterprise_customer.uuid
    if 'enterprise_customer_slug' in command_kwargs:
        command_kwargs['enterprise_customer_slug'] = testcase.enterprise_customer.slug
    command_kwargs['user1'] = testcase.user1
    command_kwargs['user2'] = testcase.user2
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
    for user in [testcase.user1, testcase.user2]:
        # Third Party API remote_id response
        responses.add(
            responses.GET,
            urljoin(lms_api.ThirdPartyAuthApiClient.API_BASE_URL,
                    "providers/{provider}/users?username={user}".format(provider=testcase.identity_provider,
                                                                        user=user.username)),
            match_querystring=True,
            json={"results": [{'username': user.username, 'remote_id': 'remote-user-id'}]},
        )

        # Course API course_details response
        responses.add(
            responses.GET,
            urljoin(lms_api.CourseApiClient.API_BASE_URL,
                    "courses/{course}/".format(course=testcase.course_id)),
            json={
                "course_id": COURSE_ID,
                "pacing": "self" if self_paced else "instructor",
                "end": end_date.isoformat() if end_date else None,
            },
        )

        # Grades API course_grades response
        responses.add(
            responses.GET,
            urljoin(lms_api.GradesApiClient.API_BASE_URL,
                    "courses/{course}/?username={user}".format(course=testcase.course_id,
                                                               user=user.username)),
            match_querystring=True,
            json=[{
                "username": user.username,
                "course_id": COURSE_ID,
                "passed": passed,
            }],
        )

        # Enrollment API enrollment response
        responses.add(
            responses.GET,
            urljoin(lms_api.EnrollmentApiClient.API_BASE_URL,
                    "enrollment/{username},{course_id}".format(username=user.username,
                                                               course_id=testcase.course_id)),
            match_querystring=True,
            json={"mode": "verified"},
        )

        # Certificates API course_grades response
        if certificate:
            responses.add(
                responses.GET,
                urljoin(lms_api.CertificatesApiClient.API_BASE_URL,
                        "certificates/{user}/courses/{course}/".format(course=testcase.course_id,
                                                                       user=user.username)),
                json=certificate,
            )
        else:
            responses.add(
                responses.GET,
                urljoin(lms_api.CertificatesApiClient.API_BASE_URL,
                        "certificates/{user}/courses/{course}/".format(course=testcase.course_id,
                                                                       user=user.username)),
                status=404,
            )


def get_expected_output(cmd_kwargs, certificate, self_paced, passed, **expected_completion):
    """
    Returns the expected JSON record logged by the ``transmit_learner_data`` command.
    """
    action = 'Successfully sent completion status call for'
    action2 = 'Skipping previously sent'
    if expected_completion['timestamp'] == NOW_TIMESTAMP:
        degreed_timestamp = '"{}"'.format(NOW_TIMESTAMP_FORMATTED)
    elif expected_completion['timestamp'] == PAST_TIMESTAMP:
        degreed_timestamp = '"{}"'.format(PAST_TIMESTAMP_FORMATTED)
    else:
        degreed_timestamp = 'null'
        action = 'Skipping in-progress'
        action2 = action

    degreed_output_template = (
        '{{'
        '"completions": [{{'
        '"completionDate": {timestamp}, '
        '"email": "{user_email}", '
        '"id": "{course_id}"'
        '}}], '
        '"orgCode": "Degreed Company"'
        '}}'
    )
    sapsf_output_template = (
        '{{'
        '"completedTimestamp": {timestamp}, '
        '"courseCompleted": "{completed}", '
        '"courseID": "{course_id}", '
        '"grade": "{grade}", '
        '"providerID": "{provider_id}", '
        '"totalHours": {total_hours}, '
        '"userID": "{user_id}"'
        '}}'
    )
    if certificate:
        expected_output = [
            # SAPSF
            "[Integrated Channel] Batch processing learners for integrated channel. Configuration:"
            " <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments:",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime(certificate.get('created_date')),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=certificate.get('is_passing'),
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action2),
            "Course details already found:",
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime(certificate.get('created_date')),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=certificate.get('is_passing'),
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>, "
            "Duration: 0.0",

            # Degreed
            "[Integrated Channel] Batch processing learners for integrated channel."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments: ",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime(certificate.get('created_date')),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=certificate.get('is_passing'),
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action2),
            "Course details already found:",
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime(certificate.get('created_date')),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=certificate.get('is_passing'),
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>,"
            " Duration: 0.0"
        ]
    elif not self_paced:
        expected_output = [
            # SAPSF
            "[Integrated Channel] Batch processing learners for integrated channel. Configuration:"
            " <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments:",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Certificate data not found."
            " Course: {course_id}, EnterpriseEnrollment: 2, Username: {username}".format(
                course_id=COURSE_ID,
                username=cmd_kwargs.get('user1')
            ),
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime('19-10-10'),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action2),
            "Course details already found:",
            "[Integrated Channel] Certificate data not found."
            " Course: {course_id}, EnterpriseEnrollment: 3, Username: {username}".format(
                course_id=COURSE_ID,
                username=cmd_kwargs.get('user2')
            ),
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime('19-10-10'),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>, "
            "Duration: 0.0",

            # Degreed 18
            "[Integrated Channel] Batch processing learners for integrated channel."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments:",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Certificate data not found."
            " Course: {course_id}, EnterpriseEnrollment: 2, Username: {username}".format(
                course_id=COURSE_ID,
                username=cmd_kwargs.get('user1')
            ),
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime('19-10-10'),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action2),
            "[Integrated Channels] Currently exporting for course:",
            "[Integrated Channel] Certificate data not found."
            " Course: {course_id}, EnterpriseEnrollment: 3, Username: {username}".format(
                course_id=COURSE_ID,
                username=cmd_kwargs.get('user2')
            ),
            "[Integrated Channel] Received data from certificate api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=parse_datetime('19-10-10'),
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>,"
            " Duration: 0.0"
        ]
    else:
        if expected_completion.get('timestamp') != 'null':
            timestamp = expected_completion.get('timestamp') / 1000
            completed_date = str(datetime.utcfromtimestamp(timestamp)) + '+00:00'
        else:
            completed_date = None
        expected_output = [
            # SAPSF
            "[Integrated Channel] Batch processing learners for integrated channel. Configuration:"
            " <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments:",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Received data from grades api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=completed_date,
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 2".format(action2),
            "[Integrated Channels] Currently exporting for course:",
            "[Integrated Channel] Received data from grades api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=completed_date,
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_KEY,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + sapsf_output_template.format(
                user_id='remote-user-id',
                course_id=COURSE_ID,
                provider_id="SAP",
                **expected_completion
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>, "
            "Duration: 0.0",

            # Degreed
            "[Integrated Channel] Batch processing learners for integrated channel."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
            "[Integrated Channel] Beginning export of enrollments:",
            "[Integrated Channel] Successfully retrieved course details for course:",
            "[Integrated Channel] Received data from grades api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=completed_date,
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user1').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 2".format(action2),
            "[Integrated Channels] Currently exporting for course:",
            "[Integrated Channel] Received data from grades api.  CompletedDate:"
            " {completed_date}, Course: {course_id}, Enterprise: {enterprise_slug}, Grade: {grade},"
            " IsPassing: {is_passing}, User: {user_id}".format(
                completed_date=completed_date,
                course_id=COURSE_ID,
                enterprise_slug=cmd_kwargs.get('enterprise_customer_slug'),
                is_passing=passed,
                user_id=cmd_kwargs.get('user2').id,
                **expected_completion
            ),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_KEY,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action),
            "Attempting to transmit serialized payload: " + degreed_output_template.format(
                user_email='example2@email.com',
                course_id=COURSE_ID,
                timestamp=degreed_timestamp
            ),
            "{} enterprise enrollment 3".format(action2),
            "[Integrated Channel] Batch learner data transmission task finished."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>,"
            " Duration: 0.0"
        ]
    return expected_output


@ddt.ddt
@mark.django_db
class TestLearnerDataTransmitIntegration(unittest.TestCase):
    """
    Integration tests for learner data transmission.
    """

    def setUp(self):
        super().setUp()

        # pylint: disable=invalid-name
        # Degreed
        degreed_create_course_completion = mock.patch(
            'integrated_channels.degreed.client.DegreedAPIClient.create_course_completion'
        )
        self.degreed_create_course_completion = degreed_create_course_completion.start()
        self.degreed_create_course_completion.return_value = 200, '{}'
        self.addCleanup(degreed_create_course_completion.stop)

        # SAPSF
        sapsf_get_oauth_access_token_mock = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token'
        )
        self.sapsf_get_oauth_access_token_mock = sapsf_get_oauth_access_token_mock.start()
        self.sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        self.addCleanup(sapsf_get_oauth_access_token_mock.stop)
        sapsf_create_course_completion = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_course_completion'
        )
        self.sapsf_create_course_completion = sapsf_create_course_completion.start()
        self.sapsf_create_course_completion.return_value = 200, '{}'
        self.addCleanup(sapsf_create_course_completion.stop)
        # pylint: enable=invalid-name

        # Course Catalog API Client
        course_catalog_api_client_mock = mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
        self.course_catalog_client = course_catalog_api_client_mock.start()
        self.addCleanup(course_catalog_api_client_mock.stop)

    @responses.activate
    @ddt.data(
        # Certificate marks course completion
        ({'enterprise_customer_slug': None}, MOCK_PASSING_CERTIFICATE, False, None, False,
         CERTIFICATE_PASSING_COMPLETION),
        ({'enterprise_customer_slug': None}, MOCK_FAILING_CERTIFICATE, False, None, False,
         CERTIFICATE_FAILING_COMPLETION),

        # enterprise_customer UUID gets filled in below
        ({'enterprise_customer': None, 'enterprise_customer_slug': None}, MOCK_PASSING_CERTIFICATE, False, None, False,
         CERTIFICATE_PASSING_COMPLETION),
        ({'enterprise_customer': None, 'enterprise_customer_slug': None}, MOCK_FAILING_CERTIFICATE, False, None, False,
         CERTIFICATE_FAILING_COMPLETION),

        # Instructor-paced course with no certificates issued yet results in incomplete course data
        ({'enterprise_customer_slug': None}, None, False, None, False,
         {'completed': 'false', 'timestamp': 'null', 'grade': 'In Progress', 'total_hours': 0.0}),

        # Self-paced course with no end date send grade=Pass, or grade=In Progress, depending on current grade.
        ({'enterprise_customer_slug': None}, None, True, None, False,
         {'completed': 'false', 'timestamp': 'null', 'grade': 'In Progress', 'total_hours': 0.0}),
        ({'enterprise_customer_slug': None}, None, True, None, True,
         {'completed': 'true', 'timestamp': NOW_TIMESTAMP, 'grade': 'Pass', 'total_hours': 0.0}),

        # Self-paced course with future end date sends grade=Pass, or grade=In Progress, depending on current grade.
        ({'enterprise_customer_slug': None}, None, True, FUTURE, False,
         {'completed': 'false', 'timestamp': 'null', 'grade': 'In Progress', 'total_hours': 0.0}),
        ({'enterprise_customer_slug': None}, None, True, FUTURE, True,
         {'completed': 'true', 'timestamp': NOW_TIMESTAMP, 'grade': 'Pass', 'total_hours': 0.0}),

        # Self-paced course with past end date sends grade=Pass, or grade=Fail, depending on current grade.
        ({'enterprise_customer_slug': None}, None, True, PAST, False,
         {'completed': 'false', 'timestamp': PAST_TIMESTAMP, 'grade': 'Fail', 'total_hours': 0.0}),
        ({'enterprise_customer_slug': None}, None, True, PAST, True,
         {'completed': 'true', 'timestamp': PAST_TIMESTAMP, 'grade': 'Pass', 'total_hours': 0.0}),
    )
    @ddt.unpack
    @skip(
        "This test is hard coding log order and OC team needs more comprehensive logs for staging. "
        "Will be restore after completed staging testing."
    )
    def test_transmit_learner_data(
            self,
            command_kwargs,
            certificate,
            self_paced,
            end_date,
            passed,
            expected_completion,
    ):
        """
        Test the log output from a successful run of the transmit_learner_data management command,
        using all the ways we can invoke it.
        """

        setup_course_catalog_api_client_mock(
            self.course_catalog_client,
            course_overrides={
                'course_id': COURSE_ID,
                'end': end_date.isoformat() if end_date else None,
                'pacing': 'self' if self_paced else 'instructor'
            }
        )
        with transmit_learner_data_context(command_kwargs, certificate, self_paced, end_date, passed) as (args, kwargs):
            with LogCapture(level=logging.DEBUG) as log_capture:
                expected_output = get_expected_output(
                    command_kwargs, certificate, self_paced, passed, **expected_completion)
                call_command('transmit_learner_data', *args, **kwargs)
                # get the list of logs just in this repo
                enterprise_log_messages = []
                for record in log_capture.records:
                    pathname = record.pathname
                    if 'edx-enterprise' in pathname and 'site-packages' not in pathname:
                        enterprise_log_messages.append(record.getMessage())
                for index, message in enumerate(expected_output):
                    assert message in enterprise_log_messages[index]


@mark.django_db
@ddt.ddt
class TestUnlinkSAPLearnersManagementCommand(unittest.TestCase, EnterpriseMockMixin, CourseDiscoveryApiTestMixin):
    """
    Test the ``unlink_sap_learners`` management command.
    """

    def setUp(self):
        self.user = factories.UserFactory(username='C-3PO')
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Veridian Dynamics',
        )
        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='ubc-bestrun',
        )
        self.degreed = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            key='key',
            secret='secret',
            degreed_company_id='Degreed Company',
            degreed_base_url='https://www.degreed.com/',
        )
        self.sapsf = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )
        self.sapsf_global_configuration = factories.SAPSuccessFactorsGlobalConfigurationFactory(
            search_student_api_path='learning/odatav4/searchStudent/v1/Students'
        )
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        self.learner = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.learner,
            course_id=self.course_run_id,
        )
        factories.DataSharingConsentFactory(
            enterprise_customer=self.enterprise_customer,
            username=self.user.username,
            course_id=self.course_run_id
        )
        self.sap_search_student_url = \
            '{sapsf_base_url}/{search_students_path}?$filter={search_filter}&$select=studentID'.format(
                sapsf_base_url=self.sapsf.sapsf_base_url.rstrip('/'),
                search_students_path=self.sapsf_global_configuration.search_student_api_path.rstrip('/'),
                search_filter=quote('criteria/isActive eq False'),
            )
        self.search_student_paginated_url = '{sap_search_student_url}&{pagination_criterion}'.format(
            sap_search_student_url=self.sap_search_student_url,
            pagination_criterion='$count=true&$top={page_size}&$skip={start_at}'.format(
                page_size=500,
                start_at=0,
            ),
        )
        super().setUp()

    @responses.activate
    def test_unlink_inactive_sap_learners_task_with_no_sap_channel(self):
        """
        Test the unlink inactive learners task without any SAP integrated channel.
        """
        # Remove all SAP integrated channels but keep Degreed integrated channels
        SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.all().delete()

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('unlink_inactive_sap_learners')

            # Because there are no SAP IntegratedChannels, the process will
            # end without any processing.
            assert not log_capture.records

    @responses.activate
    @ddt.data(
        (
            ['C-3PO', 'Only-Edx-Learner', 'Always-Active-sap-learner'],
            ['C-3PO', 'Only-Edx-Learner', 'Only-Inactive-Sap-Learner'],
            ['C-3PO'],
        )
    )
    @ddt.unpack
    @freeze_time(NOW)
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_user_from_social_auth')
    @mock.patch('enterprise.utils.get_identity_provider')
    def test_unlink_inactive_sap_learners_task_success(
            self,
            lms_learners,
            inactive_sap_learners,
            unlinked_sap_learners,
            get_identity_provider_mock,
            get_user_from_social_auth_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):
        """
        Test the unlink inactive sap learners task with valid inactive learners.
        """
        for learner_username in lms_learners:
            if User.objects.filter(username=learner_username).count() == 0:
                factories.UserFactory(username=learner_username)

        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        def mock_get_user_social_auth(*args):
            """DRY method to raise exception for invalid users."""
            uname = args[1]
            return User.objects.filter(username=uname).first()

        get_user_from_social_auth_mock.side_effect = mock_get_user_social_auth
        get_identity_provider_mock.return_value = mock.MagicMock(backend_name='tpa_saml', provider_id='saml-default')

        # Now mock SAPSF searchStudent call for learners with pagination
        for response_page, inactive_learner in enumerate(inactive_sap_learners):
            search_student_paginated_url = '{sap_search_student_url}&{pagination_criterion}'.format(
                sap_search_student_url=self.sap_search_student_url,
                pagination_criterion='$count=true&$top={page_size}&$skip={start_at}'.format(
                    page_size=500,
                    start_at=500 * response_page,
                )
            )
            sapsf_search_student_response = {
                '@odata.metadataEtag': 'W/"17090d86-20fa-49c8-8de0-de1d308c8b55"',
                "@odata.count": 500 * len(inactive_sap_learners),
                'value': [{'studentID': inactive_learner}]
            }
            responses.add(
                responses.GET,
                url=search_student_paginated_url,
                json=sapsf_search_student_response,
                status=200,
                content_type='application/json',
            )

        # Glass box test: inspect that internals of this process are doing what we expect:
        with mock.patch.object(SAPSuccessFactorsEnterpriseCustomerConfiguration,
                               'unlink_inactive_learners',
                               wraps=self.sapsf.unlink_inactive_learners) as mock_unlink_inactive_learners:
            get_inactive_learners_fx = SapSuccessFactorsLearnerManger(self.sapsf).client.get_inactive_sap_learners
            spy = ReturnValueSpy(get_inactive_learners_fx)  # create a spy to store the return value when called
            # Send in our spy to use instead:
            with mock.patch.object(SAPSuccessFactorsAPIClient,
                                   'get_inactive_sap_learners',
                                   wraps=spy) as mock_get_inactive_learners:
                call_command('unlink_inactive_sap_learners')
                # Verify that management command uses the correct SAP config object
                mock_unlink_inactive_learners.assert_any_call()
                # Verify that when we DID try to unlink the inactive learners, inactive learners were found to unlink:
                mock_get_inactive_learners.assert_any_call()
                assert len(spy.return_values[0]) == len(inactive_sap_learners)

        # Now verify that only inactive SAP learners have been unlinked
        for unlinked_sap_learner_username in unlinked_sap_learners:
            learner = User.objects.get(username=unlinked_sap_learner_username)
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=self.enterprise_customer, user_id=learner.id
            ).count() == 0

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_unlink_inactive_sap_learners_task_sapsf_failure(
            self,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):
        """
        Test the unlink inactive sap learners task with failed response from SAPSF.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow() + DAY_DELTA
        sapsf_update_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        # Note: because we didn't use 'responses.add' in unit test, ANY request library call
        # made will throw a ConnectionError. See https://github.com/getsentry/responses/blob/master/README.rst
        # What we're verifying here is that our call will still complete because the ConnectionError gets caught:
        call_command('unlink_inactive_sap_learners')
        assert True

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('enterprise.utils.get_identity_provider')
    def test_unlink_inactive_sap_learners_task_identity_failure(
            self,
            get_identity_provider_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):
        """
        Test the unlink inactive sap learners task with failed response for no identity provider.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow() + DAY_DELTA
        sapsf_update_content_metadata_mock.return_value = 200, '{}'

        # Delete the identity providers
        EnterpriseCustomerIdentityProvider.objects.all().delete()

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)
        get_identity_provider_mock.return_value = None

        # Now mock SAPSF searchStudent for inactive learner
        responses.add(
            responses.GET,
            url=self.search_student_paginated_url,
            json={
                '@odata.metadataEtag': 'W/"17090d86-20fa-49c8-8de0-de1d308c8b55"',
                "@odata.count": 1,
                'value': [{'studentID': self.user.username}]
            },
            status=200,
            content_type='application/json',
        )

        # Glass box test: inspect that internals of this process are doing what we expect:
        with mock.patch.object(SAPSuccessFactorsEnterpriseCustomerConfiguration,
                               'unlink_inactive_learners',
                               wraps=self.sapsf.unlink_inactive_learners) as mock_unlink_inactive_learners:
            get_providers_fx = SapSuccessFactorsLearnerManger(self.sapsf)._get_identity_providers  # pylint: disable=protected-access
            provider_spy = ReturnValueSpy(get_providers_fx)  # create a spy to store the return value when called

            get_inactive_learners_fx = SapSuccessFactorsLearnerManger(self.sapsf).client.get_inactive_sap_learners
            spy = ReturnValueSpy(get_inactive_learners_fx)  # create a spy to store the return value when called
            # Send in our spies to use instead:
            with mock.patch.object(SAPSuccessFactorsAPIClient,
                                   'get_inactive_sap_learners',
                                   wraps=spy) as mock_get_inactive_learners:
                with mock.patch.object(SapSuccessFactorsLearnerManger,
                                       '_get_identity_providers',
                                       wraps=provider_spy) as mock_get_providers:

                    call_command('unlink_inactive_sap_learners')
                    # Verify that management command uses the correct SAP config object
                    mock_unlink_inactive_learners.assert_any_call()
                    # Verify that when we DID try to unlink the inactive learners,
                    #  1 inactive learner (with config name self.user.username)
                    # was found to unlink
                    mock_get_inactive_learners.assert_any_call()
                    assert spy.return_values[0][0]['studentID'] == self.user.username

                    # Verify that we checked and then detected that an Enterprise has no associated identity provider:
                    mock_get_providers.assert_any_call()
                    assert provider_spy.return_values[0] is None

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_unlink_inactive_sap_learners_task_sapsf_error_response(
            self,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):
        """
        Test the unlink inactive sap learners task with error response from SAPSF catches the error
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        # Now mock SAPSF searchStudent for inactive learner
        responses.add(
            responses.GET,
            url=self.search_student_paginated_url,
            json={
                'error': {
                    'message': (
                        "The property 'InvalidProperty', used in a query expression, "
                        "is not defined in type 'com.sap.lms.odata.Student'."
                    ),
                    'code': None
                }
            },
            status=400,
            content_type='application/json',
        )

        call_command('unlink_inactive_sap_learners')
        calls_to_search_url = [c for c in responses.calls if
                               c.request.url.startswith(self.search_student_paginated_url)]

        # Test that we called the erroring out URL, but that we caught the error
        # (because the previous call_command did not error out with an exception)
        assert len(calls_to_search_url) > 0


@mark.django_db
@ddt.ddt
class TestAssignSkillstoDegreedCoursesManagementCommand(unittest.TestCase):
    """
    Test the ``assign_skills_to_degreed_courses`` management command.
    """

    def setUp(self):
        self.user = factories.UserFactory(username='C-3PO')
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            active=True,
            name='Degreed Customer',
        )
        self.enterprise_customer_2 = factories.EnterpriseCustomerFactory(
            active=True,
            name='Degreed Customer 2',
        )
        self.enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_catalog_2 = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer_2,
        )
        self.degreed_config = factories.Degreed2EnterpriseCustomerConfigurationFactory(

            enterprise_customer=self.enterprise_customer,
            degreed_base_url='http://betatest.degreed.com/',
        )
        self.degreed_config_2 = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_2,
            degreed_base_url='http://betatest.degreed.com/',
        )
        super().setUp()

    @responses.activate
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.assign_course_skills')
    def test_assign_skills_command(
            self,
            mock_degreed2_client,
            mock_enterprise_catalog_client
    ):
        """
        Test the unlink inactive learners task without any SAP integrated channel.
        """
        mock_degreed2_client.return_value = 201, '{}'
        mock_enterprise_catalog_client.return_value = [FAKE_COURSE_TO_CREATE, FAKE_COURSE_TO_CREATE_2]
        with LogCapture(level=logging.INFO) as log:
            log_message = '[Degreed Skills] Attempting to assign skills for customer'
            call_command('assign_skills_to_degreed_courses', '--catalog_user', self.user.username)
            assert log_message in log.records[-1].getMessage()
            # should make a call for two courses for both degreed enterprises with active config
            self.assertEqual(mock_degreed2_client.call_count, 4)


@ddt.ddt
@mark.django_db
class TestUpdateRoleAssignmentsCommand(unittest.TestCase):
    """
    Test the `update_role_assignments_with_customers`  management command.
    """
    @factory.django.mute_signals(signals.post_save)
    def setUp(self):
        super().setUp()
        self.cleanup_test_objects()
        self.alice = factories.UserFactory(username='alice')
        self.bob = factories.UserFactory(username='bob')
        self.clarice = factories.UserFactory(username='clarice')
        self.dexter = factories.UserFactory(username='dexter')

        # elaine is an extra user we won't link to any customer
        self.elaine = factories.UserFactory(username='elaine')

        self.alpha_customer = factories.EnterpriseCustomerFactory(
            name='alpha',
        )
        self.beta_customer = factories.EnterpriseCustomerFactory(
            name='beta',
        )

        linkages = [
            (self.alice, self.alpha_customer, roles_api.learner_role()),
            (self.alice, self.beta_customer, roles_api.admin_role()),
            (self.bob, self.alpha_customer, roles_api.learner_role()),
            (self.clarice, self.beta_customer, roles_api.admin_role()),
        ]

        for linked_user, linked_customer, role in linkages:
            factories.EnterpriseCustomerUserFactory(
                user_id=linked_user.id,
                enterprise_customer=linked_customer,
            )
            factories.SystemWideEnterpriseUserRoleAssignment(
                user=linked_user,
                role=role,
                enterprise_customer=linked_customer,
            ).save()

        # Make dexter an openedx operator without an explicit link to an enterprise
        factories.SystemWideEnterpriseUserRoleAssignment(
            user=self.dexter,
            role=roles_api.openedx_operator_role(),
        ).save()

        self.addCleanup(self.cleanup_test_objects)

    def cleanup_test_objects(self):
        """
        Helper to delete all instances of role assignments, ECUs, Enterprise customers, and Users.
        """
        SystemWideEnterpriseUserRoleAssignment.objects.all().delete()
        EnterpriseCustomerUser.objects.all().delete()
        EnterpriseCustomer.objects.all().delete()
        User.objects.all().delete()

    def _learner_assertions(self, expected_customer=None):
        """ Helper to assert that expected enterprise learner are assigned to expected customers. """
        # AED: 2021-02-12
        # Because Alice is linked to both the alpha and beta customer, and was assigned
        # an enterprise_learner role with a null enterprise_customer,
        # the management command will give Alice an explicit assignment
        # of the learner role on BOTH the alpha and betacustomer, because that dual assignment
        # is currently implied (at the time of this writing).
        expected_user_customer_assignments = [
            {'user': self.alice, 'enterprise_customer': self.alpha_customer},
            {'user': self.alice, 'enterprise_customer': self.beta_customer},
            {'user': self.bob, 'enterprise_customer': self.alpha_customer},
        ]
        if expected_customer:
            expected_user_customer_assignments = [
                assignment for assignment in expected_user_customer_assignments
                if assignment['enterprise_customer'] == expected_customer
            ]

        for assignment_kwargs in expected_user_customer_assignments:
            assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
                role=roles_api.learner_role(),
                applies_to_all_contexts=False,
                **assignment_kwargs,
            ).count() == 1

        queryset = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role=roles_api.learner_role(),
        ).exclude(
            enterprise_customer__isnull=True
        )
        if expected_customer:
            queryset = queryset.filter(enterprise_customer=expected_customer)
        assert len(expected_user_customer_assignments) == queryset.count()

    def _admin_assertions(self, expected_customer=None):
        """ Helper to assert that expected enterprise admins are assigned to expected customers. """
        # AED: 2021-02-12
        # Because Alice is linked to both the alpha and beta customer, and was assigned
        # an enterprise_admin role with a null enterprise_customer,
        # the management command will give Alice an explicit assignment
        # of the admin role on BOTH the alpha and betacustomer, because that dual assignment
        # is currently implied (at the time of this writing).
        expected_user_customer_assignments = [
            {'user': self.alice, 'enterprise_customer': self.alpha_customer},
            {'user': self.alice, 'enterprise_customer': self.beta_customer},
            {'user': self.clarice, 'enterprise_customer': self.beta_customer},
        ]
        if expected_customer:
            expected_user_customer_assignments = [
                assignment for assignment in expected_user_customer_assignments
                if assignment['enterprise_customer'] == expected_customer
            ]

        for assignment_kwargs in expected_user_customer_assignments:
            assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
                role=roles_api.admin_role(),
                applies_to_all_contexts=False,
                **assignment_kwargs,
            ).count() == 1

        queryset = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role=roles_api.admin_role()
        ).exclude(
            enterprise_customer__isnull=True
        )
        if expected_customer:
            queryset = queryset.filter(enterprise_customer=expected_customer)
        assert len(expected_user_customer_assignments) <= queryset.count()

    def _operator_assertions(self):
        """ Helper to assert that expected enterprise operators have `applies_to_all_contexts=True`. """
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.dexter,
            role=roles_api.openedx_operator_role(),
            enterprise_customer=None,
            applies_to_all_contexts=True,
        ).count() == 1

        # assert that there are no other openedx operator assignments
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role=roles_api.openedx_operator_role()
        ).count() == 1

    def test_command_no_args(self):
        """
        Calling the command with no args should process every linked user and role.
        """
        call_command('update_role_assignments_with_customers')
        self._admin_assertions()
        self._learner_assertions()
        self._operator_assertions()

    @ddt.data(
        ENTERPRISE_LEARNER_ROLE, ENTERPRISE_ADMIN_ROLE, ENTERPRISE_OPERATOR_ROLE
    )
    def test_command_with_role_argument(self, role_name):
        assertions_by_role = {
            ENTERPRISE_LEARNER_ROLE: self._learner_assertions,
            ENTERPRISE_ADMIN_ROLE: self._admin_assertions,
            ENTERPRISE_OPERATOR_ROLE: self._operator_assertions,
        }
        call_command('update_role_assignments_with_customers', '--role', role_name)
        assertions_by_role[role_name]()

    def test_command_with_customer_uuid_argument(self):
        call_command(
            'update_role_assignments_with_customers',
            '--enterprise-customer-uuid',
            self.alpha_customer.uuid,
        )

        self._admin_assertions(self.alpha_customer)
        self._learner_assertions(self.alpha_customer)
        self._operator_assertions()


@ddt.ddt
@mark.django_db
class TestBackfillLearnerRoleAssignmentsCommand(unittest.TestCase):
    """
    Test the `backfill_role_assignments`  management command.
    """
    @factory.django.mute_signals(signals.post_save)
    def setUp(self):
        super().setUp()
        self.cleanup_test_objects()

        for i in range(100):
            factories.UserFactory(username=f'user-{i}')

        self.alpha_customer = factories.EnterpriseCustomerFactory(
            name='alpha',
        )
        self.beta_customer = factories.EnterpriseCustomerFactory(
            name='beta',
        )

        users = User.objects.all()

        # Make a bunch of users for an ENT customer
        for index, user in enumerate(users[0:30]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.alpha_customer,
            )
            # make half of them have a systemwideUserRoleAssignment
            if index % 2:
                factories.SystemWideEnterpriseUserRoleAssignment(
                    user=user,
                    role=roles_api.learner_role(),
                    enterprise_customer=self.alpha_customer,
                ).save()

        # Make a bunch of users for another ENT customer
        for index, user in enumerate(users[30:65]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.beta_customer,
            )
            # make half of them have a systemwideUserRoleAssignment
            if index % 2:
                factories.SystemWideEnterpriseUserRoleAssignment(
                    user=user,
                    role=roles_api.learner_role(),
                    enterprise_customer=self.beta_customer,
                ).save()

        # Make some users that are NOT LINKED, so we should ignore them
        for index, user in enumerate(users[65:75]):
            ecu = factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.alpha_customer,
            )
            ecu.linked = False
            ecu.save()

        # Now make a subset of first set of enterprise customers also have
        # EnterpriseCustomerUser records with a 2nd enterprise customer
        for index, user in enumerate(users[0:15]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.beta_customer,
            )
            # make half of them have a systemwideUserRoleAssignment
            if index % 2:
                factories.SystemWideEnterpriseUserRoleAssignment(
                    user=user,
                    role=roles_api.learner_role(),
                    enterprise_customer=self.beta_customer,
                ).save()

        self.addCleanup(self.cleanup_test_objects)

    def test_user_role_assignments_created(self):
        """
        Verify that the management command correctly creates User Role Assignments
        for enterprise customer users missing them.
        """

        assert EnterpriseCustomerUser.all_objects.count() == 90
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=self.alpha_customer
        ).count() == 15
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=self.beta_customer
        ).count() == 24

        call_command(
            'backfill_learner_role_assignments',
            '--batch-sleep',
            '0',
            '--batch-limit',
            '10',
        )

        # Notice the discrepancy of values: 90 != 30 + 50
        # That's because 10 ECU records are linked=False, so we dont
        # create a role assignment for them
        assert EnterpriseCustomerUser.all_objects.count() == 90
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=self.alpha_customer
        ).count() == 30
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=self.beta_customer
        ).count() == 50
        for ecu in EnterpriseCustomerUser.objects.all():
            assert SystemWideEnterpriseUserRoleAssignment.objects.filter(user=ecu.user).exists()

    def cleanup_test_objects(self):
        """
        Helper to delete all instances of role assignments, ECUs, Enterprise customers, and Users.
        """
        SystemWideEnterpriseUserRoleAssignment.objects.all().delete()
        EnterpriseCustomerUser.objects.all().delete()
        EnterpriseCustomer.objects.all().delete()
        User.objects.all().delete()


@mark.django_db
@ddt.ddt
class TestBackfillCSODJoinKeysManagementCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``backfill_missing_csod_foreign_keys`` management command.
    """

    def setUp(self):
        self.cleanup_test_objects()
        self.cornerstone_base_url_one = 'https://edx.example.com/'
        self.csod_config_one = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            cornerstone_base_url=self.cornerstone_base_url_one
        )
        self.cornerstone_base_url_two = 'https://edx-stg.example.com/'
        self.csod_config_two = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            cornerstone_base_url=self.cornerstone_base_url_two
        )
        self.addCleanup(self.cleanup_test_objects)
        super().setUp()

    def tearDown(self):
        self.cleanup_test_objects()
        super().tearDown()

    def test_not_found(self):
        """
        Verify that the management command does not adjust records when evaluating a subdomain with no config having a
        corresponding base url
        """
        factories.CornerstoneLearnerDataTransmissionAuditFactory(
            subdomain='should-not-exist',
            plugin_configuration_id=None
        )
        call_command(
            'backfill_missing_csod_foreign_keys',
        )
        assert 1 == CornerstoneLearnerDataTransmissionAudit.objects.filter(plugin_configuration_id__isnull=True).count()

    def test_duplicate_config_found(self):
        """
        Verify that the management command does not adjust records when evaluating a subdomain with multiple configs
        having a corresponding base url
        """
        # a CSOD config with duplicate domain
        factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            cornerstone_base_url=self.cornerstone_base_url_one
        )
        factories.CornerstoneLearnerDataTransmissionAuditFactory(
            subdomain='edx',
            plugin_configuration_id=None,
        )
        call_command(
            'backfill_missing_csod_foreign_keys',
        )
        assert 1 == CornerstoneLearnerDataTransmissionAudit.objects.filter(plugin_configuration_id__isnull=True).count()

    def test_all_one_config(self):
        """
        Verify that the management command runs when all records have the same subdomain
        """
        for _ in range(10):
            factories.CornerstoneLearnerDataTransmissionAuditFactory(subdomain='edx')
        call_command(
            'backfill_missing_csod_foreign_keys',
        )
        assert 0 == CornerstoneLearnerDataTransmissionAudit.objects.filter(plugin_configuration_id__isnull=True).count()

    def test_two_configs(self):
        """
        Verify that the management command runs with a mix of subdomains in the data
        """
        for _ in range(10):
            factories.CornerstoneLearnerDataTransmissionAuditFactory(subdomain='edx')
        for _ in range(10):
            factories.CornerstoneLearnerDataTransmissionAuditFactory(subdomain='edx-stg')
        call_command(
            'backfill_missing_csod_foreign_keys',
        )
        assert 0 == CornerstoneLearnerDataTransmissionAudit.objects.filter(plugin_configuration_id__isnull=True).count()

    def cleanup_test_objects(self):
        """
        Helper to delete all test data
        """
        CornerstoneLearnerDataTransmissionAudit.objects.all().delete()
        CornerstoneEnterpriseCustomerConfiguration.objects.all().delete()


@mark.django_db
@ddt.ddt
class TestBackfillRemoteActionTimestampsManagementCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``backfill_remote_action_timestamps`` management command.
    """

    def setUp(self):
        ContentMetadataItemTransmission.objects.all().delete()
        super().setUp()

    def test_normal_run(self):
        """
        Verify that the management command sets the new columns
        """
        factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX',
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            plugin_configuration_id=1,
            integrated_channel_code='GENERIC',
            channel_metadata={},
            remote_created_at=None,
            remote_updated_at=None,
            created=NOW,
            modified=NOW,
        )
        call_command(
            'backfill_remote_action_timestamps',
        )
        assert 0 == ContentMetadataItemTransmission.objects.filter(remote_created_at__isnull=True).count()


@mark.django_db
@ddt.ddt
class TestResetCsodRemoteDeletedAtManagementCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``reset_csod_remote_deleted_at`` management command.
    """

    def setUp(self):
        ContentMetadataItemTransmission.objects.all().delete()
        super().setUp()

    def test_normal_run(self):
        """
        Verify that the management command touches the correct objects
        """

        # a non-CSOD item we DO NOT want touched
        generic1 = factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX-GENERIC-1',
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            plugin_configuration_id=1,
            integrated_channel_code='GENERIC',
            channel_metadata={},
            remote_deleted_at=NOW,
            api_response_status_code=None,
        )
        # a CSOD item we DO want touched
        csod1 = factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX-CSOD-1',
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            plugin_configuration_id=1,
            integrated_channel_code='CSOD',
            channel_metadata={},
            remote_deleted_at=NOW,
            api_response_status_code=200,
        )
        # a CSOD item we DO want touched
        csod2 = factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX-CSOD-2',
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            plugin_configuration_id=1,
            integrated_channel_code='CSOD',
            channel_metadata={},
            remote_deleted_at=NOW,
            api_response_status_code=None,
        )

        call_command(
            'reset_csod_remote_deleted_at',
        )

        generic1.refresh_from_db()
        csod1.refresh_from_db()
        csod2.refresh_from_db()

        assert generic1.remote_deleted_at is not None
        assert csod1.remote_deleted_at is None
        assert csod2.remote_deleted_at is None


@mark.django_db
@ddt.ddt
class TestMarkOrphanedContentMetadataAuditsManagementCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``mark_orphaned_content_metadata_audits`` management command.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Veridian Dynamics',
        )
        ContentMetadataItemTransmission.objects.all().delete()
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_customer.enterprise_customer_catalogs.set([enterprise_catalog])
        self.enterprise_customer.save()
        self.customer_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )
        self.orphaned_content = factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX',
            enterprise_customer=self.enterprise_customer,
            plugin_configuration_id=self.customer_config.id,
            integrated_channel_code=self.customer_config.channel_code(),
            channel_metadata={},
            enterprise_customer_catalog_uuid=uuid.uuid4(),
            remote_created_at=datetime.now()
        )
        super().setUp()

    @override_settings(ALLOW_ORPHANED_CONTENT_REMOVAL=True)
    def test_normal_run(self):
        assert not OrphanedContentTransmissions.objects.all()
        call_command('mark_orphaned_content_metadata_audits')
        orphaned_content = OrphanedContentTransmissions.objects.first()
        assert orphaned_content.content_id == self.orphaned_content.content_id

    @override_settings(ALLOW_ORPHANED_CONTENT_REMOVAL=True)
    def test_orphaned_content_without_catalog_uuids(self):
        self.orphaned_content.enterprise_customer_catalog_uuid = None
        self.orphaned_content.save()
        assert not OrphanedContentTransmissions.objects.all()
        call_command('mark_orphaned_content_metadata_audits')
        num_orphaned_content = OrphanedContentTransmissions.objects.count()
        assert num_orphaned_content == 1


@mark.django_db
@ddt.ddt
class TestUpdateConfigLastErroredAt(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``update_config_last_errored_at`` management command.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer_1 = factories.EnterpriseCustomerFactory(
            name='Wonka Factory',
        )
        self.enterprise_customer_2 = factories.EnterpriseCustomerFactory(
            name='Hershey LLC',
        )

    def test_valid_audits(self):
        """
        Verify that non-error audits and audits outside of the time range do not clear
        out the error states
        """
        old_timestamp = datetime.now() - timedelta(days=5)
        csod_config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_1,
            last_sync_errored_at=old_timestamp,
            last_content_sync_errored_at=old_timestamp,
            last_learner_sync_errored_at=old_timestamp,
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer_1,
            plugin_configuration_id=csod_config.id,
            integrated_channel_code=csod_config.channel_code(),
            api_response_status_code=400,
            # this one is not in the time frame and should not be counted
            remote_created_at=timezone.now().date() - timedelta(days=5)
        )
        call_command(
            'update_config_last_errored_at',
        )
        csod_config.refresh_from_db()
        assert csod_config.last_sync_errored_at is None
        assert csod_config.last_content_sync_errored_at is None
        assert csod_config.last_learner_sync_errored_at is None

    def test_invalid_audits(self):
        """
        Verify that the management command runs when all records have the same subdomain
        """
        old_timestamp = datetime.now() - timedelta(days=5)
        old_timestamp = old_timestamp.replace(tzinfo=pytz.UTC)
        moodle_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_2,
            last_sync_errored_at=old_timestamp,
            last_content_sync_errored_at=old_timestamp,
            last_learner_sync_errored_at=old_timestamp,
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer_2,
            plugin_configuration_id=moodle_config.id,
            integrated_channel_code=moodle_config.channel_code(),
            api_response_status_code=400,
            remote_created_at=datetime.now()
        )
        call_command(
            'update_config_last_errored_at',
        )
        moodle_config.refresh_from_db()
        assert moodle_config.last_sync_errored_at == old_timestamp
        assert moodle_config.last_content_sync_errored_at == old_timestamp
        assert moodle_config.last_learner_sync_errored_at is None


@mark.django_db
@ddt.ddt
class TestRemoveNullCatalogTransmissionAuditsManagementCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``remove_null_catalog_transmission_audits`` management command.
    """

    def setUp(self):
        self.enterprise_customer_1 = factories.EnterpriseCustomerFactory(
            name='Wonka Factory',
        )
        self.enterprise_customer_2 = factories.EnterpriseCustomerFactory(
            name='Hershey LLC',
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer_1,
            enterprise_customer_catalog_uuid=None
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer_2,
            enterprise_customer_catalog_uuid="d9efab41-5e09-4094-977a-96313b3dca08"
        )
        super().setUp()

    def test_normal_run(self):
        assert ContentMetadataItemTransmission.objects.all().count() == 2
        call_command('remove_null_catalog_transmission_audits')
        assert ContentMetadataItemTransmission.objects.all().count() == 1
        assert ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=None
        ).count() == 0


@mark.django_db
class TestRemoveStaleIntegratedChannelAPILogsCommand(unittest.TestCase, EnterpriseMockMixin):
    """
    Test the ``remove_stale_integrated_channel_api_logs`` management command.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.pk = 1
        self.enterprise_customer_configuration_id = 1
        self.endpoint = 'https://example.com/endpoint'
        self.payload = "{}"
        self.time_taken = 500
        self.response_body = "{}"
        self.status_code = 200
        super().setUp()

    def test_remove_stale_integrated_channel_api_logs(self):
        """
        Test the remove stale integrated channel api logs command.
        """
        time_duration_value = random.randint(15, 60)
        time_threshold = timezone.now() - timedelta(days=time_duration_value)

        data = {
            'enterprise_customer': self.enterprise_customer,
            'enterprise_customer_configuration_id': self.enterprise_customer_configuration_id,
            'endpoint': self.endpoint,
            'payload': self.payload,
            'time_taken': self.time_taken,
            'response_body': self.response_body,
            'status_code': self.status_code,
            'created': time_threshold,
            'modified': time_threshold
        }

        instances = []

        num_records = 10

        for _ in range(num_records):
            instances.append(IntegratedChannelAPIRequestLogs(**data))

        IntegratedChannelAPIRequestLogs.objects.bulk_create(instances)
        data["created"] = data["modified"] = timezone.now()
        IntegratedChannelAPIRequestLogs.objects.create(**data)

        assert IntegratedChannelAPIRequestLogs.objects.all().count() == num_records + 1
        call_command('remove_stale_integrated_channel_api_logs', time_duration=time_duration_value)
        assert IntegratedChannelAPIRequestLogs.objects.all().count() == 1

        older_than_one_month = IntegratedChannelAPIRequestLogs.objects.filter(
            created__lt=time_threshold
        ).exists()
        self.assertFalse(older_than_one_month)
