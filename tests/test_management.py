# -*- coding: utf-8 -*-
"""
Test the Enterprise management commands and related functions.
"""
from __future__ import absolute_import, division, unicode_literals, with_statement

import logging
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta

import ddt
import factory
import mock
import responses
from faker import Factory as FakerFactory
from freezegun import freeze_time
from pytest import mark, raises
from requests.compat import urljoin
from testfixtures import LogCapture

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import signals
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from enterprise.api_client import lms as lms_api
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
)
from enterprise.management.commands.assign_enterprise_user_roles import Command as AssignEnterpriseUserRolesCommand
from enterprise.models import (
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.management.commands import (
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandMixin,
)
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import factories
from test_utils.fake_catalog_api import CourseDiscoveryApiTestMixin, setup_course_catalog_api_client_mock
from test_utils.fake_enterprise_api import EnterpriseMockMixin

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

    @ddt.data('SAP', 'DEGREED')
    def test_transmit_content_metadata_specific_channel(self, channel_code):
        """
        Only the channel we input is what we get out.
        """
        channel_class = INTEGRATED_CHANNEL_CHOICES[channel_code]
        assert IntegratedChannelCommandMixin.get_channel_classes(channel_code) == [channel_class]


@mark.django_db
@ddt.ddt
class TestTransmitCourseMetadataManagementCommand(unittest.TestCase, EnterpriseMockMixin, CourseDiscoveryApiTestMixin):
    """
    Test the ``transmit_content_metadata`` management command.
    """

    def setUp(self):
        self.user = factories.UserFactory(username='C-3PO')
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Veridian Dynamics',
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
        self.sapsf_global_configuration = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.catalog_api_client_mock = self._make_patch(
            self._make_catalog_api_location("CourseCatalogApiServiceClient")
        )
        super(TestTransmitCourseMetadataManagementCommand, self).setUp()

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
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.create_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.integrated_channel.management.commands.transmit_content_metadata.transmit_content_metadata.delay')  # pylint: disable=line-too-long
    def test_transmit_content_metadata_task_with_error(
            self,
            transmit_content_metadata_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
            degreed_create_content_metadata_mock,
    ):  # pylint: disable=invalid-name
        """
        Verify the data transmission task for integrated channels with error.

        Test that the management command `transmit_content_metadata` transmits
        courses metadata related to other integrated channels even if an
        integrated channel fails to transmit due to some error.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'
        degreed_create_content_metadata_mock.return_value = 200, '{}'

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
        dummy_degreed = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=dummy_enterprise_customer,
            key='key',
            secret='secret',
            degreed_company_id='Degreed Company',
            degreed_base_url='https://www.degreed.com/',
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
            mock.call('C-3PO', 'SAP', 1),
            mock.call('C-3PO', 'DEGREED', 1)
        ]

        call_command('transmit_content_metadata', '--catalog_user', 'C-3PO')

        transmit_content_metadata_mock.assert_has_calls(expected_calls, any_order=True)

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.create_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.integrated_channel.management.commands.transmit_content_metadata.transmit_content_metadata.delay')  # pylint: disable=line-too-long
    def test_transmit_content_metadata_task_success(
            self,
            transmit_content_metadata_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
            degreed_create_content_metadata_mock,
    ):  # pylint: disable=invalid-name
        """
        Test the data transmission task.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow()
        sapsf_update_content_metadata_mock.return_value = 200, '{}'
        degreed_create_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        expected_calls = [
            mock.call('C-3PO', 'SAP', 1),
            mock.call('C-3PO', 'DEGREED', 1),
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
        DegreedEnterpriseCustomerConfiguration.objects.all().delete()

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


COURSE_ID = 'course-v1:edX+DemoX+DemoCourse'
COURSE_KEY = 'edX+DemoX'

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
    grade=LearnerExporter.GRADE_PASSING,
    total_hours=0.0,
)

# Expected learner completion data from the mock failing certificate
CERTIFICATE_FAILING_COMPLETION = dict(
    completed='false',
    timestamp=NOW_TIMESTAMP,
    grade=LearnerExporter.GRADE_FAILING,
    total_hours=0.0,
)


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
        super(TestTransmitLearnerData, self).setUp()

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
    # Mock the JWT authentication for LMS API calls
    with mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock()):

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
            json=dict(results=[
                dict(username=user.username, remote_id='remote-user-id'),
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
                    "courses/{course}/?username={user}".format(course=testcase.course_id,
                                                               user=user.username)),
            match_querystring=True,
            json=[dict(
                username=user.username,
                course_id=COURSE_ID,
                passed=passed,
            )],
        )

        # Enrollment API enrollment response
        responses.add(
            responses.GET,
            urljoin(lms_api.EnrollmentApiClient.API_BASE_URL,
                    "enrollment/{username},{course_id}".format(username=user.username,
                                                               course_id=testcase.course_id)),
            match_querystring=True,
            json=dict(
                mode="verified",
            ),
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

            # Degreed
            "[Integrated Channel] Batch processing learners for integrated channel."
            " Configuration: <DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>",
            "[Integrated Channel] Starting Export. CompletedDate: None, Course: None, Grade: None,"
            " IsPassing: False, User: None",
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
        if expected_completion.get('timestamp') != u'null':
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
        super(TestLearnerDataTransmitIntegration, self).setUp()

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
        (dict(enterprise_customer_slug=None), MOCK_PASSING_CERTIFICATE, False, None, False,
         CERTIFICATE_PASSING_COMPLETION),
        (dict(enterprise_customer_slug=None), MOCK_FAILING_CERTIFICATE, False, None, False,
         CERTIFICATE_FAILING_COMPLETION),

        # enterprise_customer UUID gets filled in below
        (dict(enterprise_customer=None, enterprise_customer_slug=None), MOCK_PASSING_CERTIFICATE, False, None, False,
         CERTIFICATE_PASSING_COMPLETION),
        (dict(enterprise_customer=None, enterprise_customer_slug=None), MOCK_FAILING_CERTIFICATE, False, None, False,
         CERTIFICATE_FAILING_COMPLETION),

        # Instructor-paced course with no certificates issued yet results in incomplete course data
        (dict(enterprise_customer_slug=None), None, False, None, False,
         dict(completed='false', timestamp='null', grade='In Progress', total_hours=0.0)),

        # Self-paced course with no end date send grade=Pass, or grade=In Progress, depending on current grade.
        (dict(enterprise_customer_slug=None), None, True, None, False,
         dict(completed='false', timestamp='null', grade='In Progress', total_hours=0.0)),
        (dict(enterprise_customer_slug=None), None, True, None, True,
         dict(completed='true', timestamp=NOW_TIMESTAMP, grade='Pass', total_hours=0.0)),

        # Self-paced course with future end date sends grade=Pass, or grade=In Progress, depending on current grade.
        (dict(enterprise_customer_slug=None), None, True, FUTURE, False,
         dict(completed='false', timestamp='null', grade='In Progress', total_hours=0.0)),
        (dict(enterprise_customer_slug=None), None, True, FUTURE, True,
         dict(completed='true', timestamp=NOW_TIMESTAMP, grade='Pass', total_hours=0.0)),

        # Self-paced course with past end date sends grade=Pass, or grade=Fail, depending on current grade.
        (dict(enterprise_customer_slug=None), None, True, PAST, False,
         dict(completed='false', timestamp=PAST_TIMESTAMP, grade='Fail', total_hours=0.0)),
        (dict(enterprise_customer_slug=None), None, True, PAST, True,
         dict(completed='true', timestamp=PAST_TIMESTAMP, grade='Pass', total_hours=0.0)),
    )
    @ddt.unpack
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
        learner = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=learner,
            course_id=self.course_run_id,
        )
        factories.DataSharingConsentFactory(
            enterprise_customer=self.enterprise_customer,
            username=self.user.username,
            course_id=self.course_run_id
        )
        self.sap_search_student_url = '{sapsf_base_url}/{search_students_path}?$filter={search_filter}'.format(
            sapsf_base_url=self.sapsf.sapsf_base_url.rstrip('/'),
            search_students_path=self.sapsf_global_configuration.search_student_api_path.rstrip('/'),
            search_filter='criteria/isActive eq False&$select=studentID',
        )
        self.search_student_paginated_url = '{sap_search_student_url}&{pagination_criterion}'.format(
            sap_search_student_url=self.sap_search_student_url,
            pagination_criterion='$count=true&$top={page_size}&$skip={start_at}'.format(
                page_size=500,
                start_at=0,
            ),
        )
        super(TestUnlinkSAPLearnersManagementCommand, self).setUp()

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

    def assert_info_logs_sap_learners_unlink(self, expected_messages):
        """
        DRY method to verify log messages for management command "unlink_inactive_sap_learners".
        """
        with LogCapture(level=logging.INFO) as log_capture:
            call_command('unlink_inactive_sap_learners')
            for index, message in enumerate(expected_messages):
                assert message in log_capture.records[index].getMessage()

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
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_user_from_social_auth')
    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_identity_provider')
    def test_unlink_inactive_sap_learners_task_success(
            self,
            lms_learners,
            inactive_sap_learners,
            unlinked_sap_learners,
            get_identity_provider_mock,
            get_user_from_social_auth_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):  # pylint: disable=invalid-name
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
                u'@odata.metadataEtag': u'W/"17090d86-20fa-49c8-8de0-de1d308c8b55"',
                u"@odata.count": 500 * len(inactive_sap_learners),
                u'value': [{'studentID': inactive_learner}]
            }
            responses.add(
                responses.GET,
                url=search_student_paginated_url,
                json=sapsf_search_student_response,
                status=200,
                content_type='application/json',
            )

        expected_messages = [
            'Processing learners to unlink inactive users using configuration: [{}]'.format(self.sapsf),
            'SAP SF searchStudent API returned [1] inactive learners of total [1500] starting from [0] for '
            'enterprise customer [{}]'.format(self.enterprise_customer.name),
            'SAP SF searchStudent API returned [1] inactive learners of total [1500] starting from [500] for '
            'enterprise customer [{}]'.format(self.enterprise_customer.name),
            'SAP SF searchStudent API returned [1] inactive learners of total [1500] starting from [1000] for '
            'enterprise customer [{}]'.format(self.enterprise_customer.name),
            'Found [{}] SAP inactive learners for enterprise customer [{}]'.format(
                len(inactive_sap_learners), self.enterprise_customer.name
            ),
            'Enterprise learner {{{email}}} successfully unlinked from Enterprise '
            'Customer {{Veridian Dynamics}}'.format(email=User.objects.get(username='C-3PO').email),
            'Learner with email [{}] and SAP student id [Only-Edx-Learner] is not linked with enterprise [{}]'.format(
                User.objects.get(username='Only-Edx-Learner').email, self.enterprise_customer.name
            ),
            'No social auth data found for inactive user with SAP student id [Only-Inactive-Sap-Learner] '
            'of enterprise customer [{}] with identity provider [saml-default]'.format(self.enterprise_customer.name),
            'Unlink inactive learners task for integrated channel configuration '
            '[{}] took [0.0] seconds'.format(self.sapsf)
        ]
        self.assert_info_logs_sap_learners_unlink(expected_messages)

        # Now verify that only inactive SAP learners have been unlinked
        for unlinked_sap_learner_username in unlinked_sap_learners:
            learner = User.objects.get(username=unlinked_sap_learner_username)
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=self.enterprise_customer, user_id=learner.id
            ).count() == 0

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_unlink_inactive_sap_learners_task_sapsf_failure(
            self,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):  # pylint: disable=invalid-name
        """
        Test the unlink inactive sap learners task with failed response from SAPSF.
        """
        sapsf_get_oauth_access_token_mock.return_value = "token", datetime.utcnow() + DAY_DELTA
        sapsf_update_content_metadata_mock.return_value = 200, '{}'

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        expected_messages = [
            'Processing learners to unlink inactive users using configuration: '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Unable to fetch inactive learners from SAP searchStudent API with '
            'url "{%s}".' % self.search_student_paginated_url
        ]
        self.assert_info_logs_sap_learners_unlink(expected_messages)

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_identity_provider')
    def test_unlink_inactive_sap_learners_task_identity_failure(
            self,
            get_identity_provider_mock,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):  # pylint: disable=invalid-name
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
                u'@odata.metadataEtag': u'W/"17090d86-20fa-49c8-8de0-de1d308c8b55"',
                u"@odata.count": 1,
                u'value': [{'studentID': self.user.username}]
            },
            status=200,
            content_type='application/json',
        )

        expected_messages = [
            'Processing learners to unlink inactive users using configuration: [{}]'.format(self.sapsf),
            'SAP SF searchStudent API returned [1] inactive learners of total [1] starting from [0] '
            'for enterprise customer [{}]'.format(self.enterprise_customer.name),
            'Found [1] SAP inactive learners for enterprise customer [{}]'.format(self.enterprise_customer.name),
            'Enterprise customer [{}] has no associated identity provider'.format(self.enterprise_customer.name),
            'Unlink inactive learners task for integrated channel configuration '
            '[{}] took [0.0] seconds'.format(self.sapsf)
        ]
        self.assert_info_logs_sap_learners_unlink(expected_messages)

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_unlink_inactive_sap_learners_task_sapsf_error_response(
            self,
            sapsf_update_content_metadata_mock,
            sapsf_get_oauth_access_token_mock,
    ):  # pylint: disable=invalid-name
        """
        Test the unlink inactive sap learners task with error response from SAPSF.
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
                u'error': {
                    u'message': u"The property 'InvalidProperty', used in a query expression, "
                                u"is not defined in type 'com.sap.lms.odata.Student'.",
                    u'code': None
                }
            },
            status=400,
            content_type='application/json',
        )
        expected_messages = [
            'Processing learners to unlink inactive users using configuration: [{}]'.format(self.sapsf),
            '''SAP searchStudent API for customer Veridian Dynamics '''
            '''and base url http://enterprise.successfactors.com/ returned response with error message '''
            '''"The property 'InvalidProperty', used in '''
            '''a query expression, is not defined in type 'com.sap.lms.odata.Student'." and with error code "None".''',
            'Found [{}] SAP inactive learners for enterprise customer [{}]'.format(0, self.enterprise_customer.name),
        ]
        self.assert_info_logs_sap_learners_unlink(expected_messages)


@ddt.ddt
@mark.django_db
class TestMigrateEnterpriseUserRolesCommand(unittest.TestCase):
    """
    Test the assign_enterprise_user_roles management command.
    """
    @factory.django.mute_signals(signals.post_save)
    def setUp(self):
        super(TestMigrateEnterpriseUserRolesCommand, self).setUp()

        data_api_access_group = factories.GroupFactory(name=ENTERPRISE_DATA_API_ACCESS_GROUP)
        enrollment_api_access_group = factories.GroupFactory(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP)

        operator_user = factories.UserFactory(email='enterprise_operator@example.com', is_staff=True)
        data_api_access_group.user_set.add(operator_user)

        admin_user = factories.UserFactory(email='enterprise_admin@example.com')
        data_api_access_group.user_set.add(admin_user)

        enrollment_api_admin_user = factories.UserFactory(email='enterprise_enrollment_api_admin@example.com')
        enrollment_api_access_group.user_set.add(enrollment_api_admin_user)

        learner_user = factories.UserFactory(email='enterprise_learner@example.com')
        enterprise_customer = factories.EnterpriseCustomerFactory(
            name='Team Titans',
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=learner_user.id,
            enterprise_customer=enterprise_customer,
        )

        self.command = AssignEnterpriseUserRolesCommand()

    def _assert_role_assignments(self, user, role_name, user_role_assignment_count, is_feature_role=False):
        """
        Verify expected role assignment records are created for specific role.
        """
        role_class = SystemWideEnterpriseRole
        role_assignment_class = SystemWideEnterpriseUserRoleAssignment

        if is_feature_role:
            role_class = EnterpriseFeatureRole
            role_assignment_class = EnterpriseFeatureUserRoleAssignment

        enterprise_role = role_class.objects.get(name=role_name)
        user_role_assignments = role_assignment_class.objects.filter(
            user=user,
            role=enterprise_role
        )
        self.assertEqual(user_role_assignments.count(), user_role_assignment_count)

    @ddt.data(
        ('enterprise_admin@example.com', ENTERPRISE_ADMIN_ROLE, False),
        ('enterprise_operator@example.com', ENTERPRISE_OPERATOR_ROLE, False),
        ('enterprise_learner@example.com', ENTERPRISE_LEARNER_ROLE, False),
        ('enterprise_enrollment_api_admin@example.com', ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE, True)
    )
    @ddt.unpack
    def test_assign_enterprise_user_roles_success(self, user_email, role_name, is_feature_role):
        """
        Tests `assign_enterprise_user_roles` command runs with expected results.
        """
        user = User.objects.get(email=user_email)
        # Verify that initially there are no enterprise role assignment records.
        self._assert_role_assignments(user, role_name, 0, is_feature_role)

        # Run assign_enterprise_user_roles to assign enterprise roles.
        call_command('assign_enterprise_user_roles', '--role', role_name, batch_sleep=0)

        # Verify new respective role assignment records are created for the role.
        self._assert_role_assignments(user, role_name, 1, is_feature_role)

    @ddt.data(
        ('enterprise_admin@example.com', ENTERPRISE_ADMIN_ROLE, False),
        ('enterprise_operator@example.com', ENTERPRISE_OPERATOR_ROLE, False),
        ('enterprise_learner@example.com', ENTERPRISE_LEARNER_ROLE, False),
        ('enterprise_enrollment_api_admin@example.com', ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE, True)
    )
    @ddt.unpack
    def test_assign_enterprise_user_roles_rerun(self, user_email, role_name, is_feature_role):
        """
        Tests running `assign_enterprise_user_roles` command again gives expected results.
        """
        user = User.objects.get(email=user_email)
        # Verify that initially there are no enterprise role assignment records.
        self._assert_role_assignments(user, role_name, 0, is_feature_role)

        # Run assign_enterprise_user_roles to assign enterprise roles.
        call_command('assign_enterprise_user_roles', '--role', role_name, batch_sleep=0)

        # Verify new respective role assignment records are created for the role.
        self._assert_role_assignments(user, role_name, 1, is_feature_role)

        # Run assign_enterprise_user_roles command again.
        call_command('assign_enterprise_user_roles', '--role', role_name, )

        # Verify no new respective role assignment records are created.
        self._assert_role_assignments(user, role_name, 1, is_feature_role)

    @ddt.data(
        (
            '_get_enterprise_customer_users_batch',
            User.objects.filter(pk__in=EnterpriseCustomerUser.objects.values('user_id'))
        ),
        (
            '_get_enterprise_admin_users_batch',
            User.objects.filter(groups__name=ENTERPRISE_DATA_API_ACCESS_GROUP, is_staff=False)
        ),
        (
            '_get_enterprise_operator_users_batch',
            User.objects.filter(groups__name=ENTERPRISE_DATA_API_ACCESS_GROUP, is_staff=True)
        ),
        (
            '_get_enterprise_enrollment_api_admin_users_batch',
            User.objects.filter(groups__name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP, is_staff=False)
        )
    )
    @ddt.unpack
    def test_get_users_batch(self, get_batch_method, batch_query):
        """
        Test that batch methods should return the correct query_set based on start and end inidices provided.
        """
        start = 2
        end = 5
        expected_query = str(
            batch_query[start:end].query
        )
        actual_query = str(
            getattr(self.command, get_batch_method)(start, end).query
        )
        assert actual_query == expected_query

    def test_assign_enterprise_user_roles_invalid_role(self):
        """
        Tests `assign_enterprise_user_roles` command throws error when given invalid role name.
        """
        invalid_role_name = 'enterprise_titans'
        error = 'Please provide a valid role name. Supported roles are {admin} and {learner}'.format(
            admin=ENTERPRISE_ADMIN_ROLE,
            learner=ENTERPRISE_LEARNER_ROLE
        )
        with raises(CommandError) as excinfo:
            call_command('assign_enterprise_user_roles', '--role', invalid_role_name)
        assert str(excinfo.value) == error

    def test_assign_enterprise_user_roles_no_role(self):
        """
        Tests `assign_enterprise_user_roles` command throws error when no role is provided.
        """
        error = 'Please provide a valid role name. Supported roles are {admin} and {learner}'.format(
            admin=ENTERPRISE_ADMIN_ROLE,
            learner=ENTERPRISE_LEARNER_ROLE
        )
        with raises(CommandError) as excinfo:
            call_command('assign_enterprise_user_roles')
        assert str(excinfo.value) == error
