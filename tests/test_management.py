# -*- coding: utf-8 -*-
"""
Test the Enterprise management commands and related functions.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import logging
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta

import ddt
import mock
import responses
from faker import Factory as FakerFactory
from freezegun import freeze_time
from pytest import mark, raises
from requests.compat import urljoin
from testfixtures import LogCapture

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from enterprise.api_client import lms as lms_api
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.management.commands import (
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandMixin,
)
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import factories
from test_utils.fake_catalog_api import CourseDiscoveryApiTestMixin
from test_utils.fake_enterprise_api import EnterpriseMockMixin

NOW = datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP = 1483326245000
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')
DAY_DELTA = timedelta(days=1)
PAST = NOW - DAY_DELTA
PAST_TIMESTAMP = NOW_TIMESTAMP - 24*60*60*1000
PAST_TIMESTAMP_FORMATTED = PAST.strftime('%F')
FUTURE = NOW + DAY_DELTA


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
            catalog=1,
            name='Veridian Dynamics',
        )
        self.degreed = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            key='key',
            secret='secret',
            degreed_company_id='Degreed Company'
        )
        self.degreed_global_configuration = factories.DegreedGlobalConfigurationFactory(
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
    def test_transmit_content_metadata_task_with_error(
            self,
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

        # Mock first integrated channel with failure
        enterprise_uuid_for_failure = str(self.enterprise_customer.uuid)
        self.mock_ent_courses_api_with_error(enterprise_uuid=enterprise_uuid_for_failure)

        # Now create a new integrated channel with a new enterprise and mock
        # enterprise courses API to send failure response
        course_run_id_for_success = 'course-v1:edX+DemoX+Demo_Course_1'
        dummy_enterprise_customer = factories.EnterpriseCustomerFactory(
            catalog=1,
            name='Dummy Enterprise',
        )
        dummy_degreed = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=dummy_enterprise_customer,
            key='key',
            secret='secret',
            degreed_company_id='Degreed Company',
            active=True,
        )
        dummy_sapsf = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=dummy_enterprise_customer,
            sapsf_base_url='http://enterprise.successfactors.com/',
            key='key',
            secret='secret',
            active=True,
        )

        enterprise_uuid_for_success = str(dummy_enterprise_customer.uuid)
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=enterprise_uuid_for_success,
            course_run_ids=[course_run_id_for_success]
        )

        # Verify that first integrated channel logs failure but the second
        # integrated channel still successfully transmits courseware data.
        expected_messages = [
            # SAPSF
            'Transmitting content metadata to integrated channel using configuration: '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Transmission of content metadata failed for user [C-3PO] and for integrated channel with '
            'code [SAP] and id [1].',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                self.sapsf
            ),
            'Transmitting content metadata to integrated channel using configuration: '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Retrieved content metadata for enterprise [{}]'.format(dummy_enterprise_customer.name),
            'Exporting content metadata item with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item creation with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item update with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item deletion with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                dummy_sapsf
            ),

            # Degreed
            'Transmitting content metadata to integrated channel using configuration: '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Transmission of content metadata failed for user [C-3PO] and for integrated channel with '
            'code [DEGREED] and id [1].',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                self.degreed
            ),
            'Transmitting content metadata to integrated channel using configuration: '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Retrieved content metadata for enterprise [{}]'.format(dummy_enterprise_customer.name),
            'Exporting content metadata item with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item creation with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item update with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Preparing to transmit content metadata item deletion with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Dummy Enterprise>]',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                dummy_degreed
            )
        ]

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('transmit_content_metadata', '--catalog_user', 'C-3PO')
            for index, message in enumerate(expected_messages):
                assert message in log_capture.records[index].getMessage()

    @responses.activate
    @freeze_time(NOW)
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.create_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_content_metadata_task_success(
            self,
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

        uuid = str(self.enterprise_customer.uuid)
        course_run_ids = ['course-v1:edX+DemoX+Demo_Course_1', 'course-v1:edX+DemoX+Demo_Course_2']
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=uuid,
            course_run_ids=course_run_ids[:1]
        )

        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        expected_messages = [
            # SAPSF
            'Transmitting content metadata to integrated channel using configuration: '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Retrieved content metadata for enterprise [{}]'.format(self.enterprise_customer.name),
            'Exporting content metadata item with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item creation with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item update with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item deletion with plugin configuration '
            '[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                self.sapsf
            ),

            # Degreed
            'Transmitting content metadata to integrated channel using configuration: '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Retrieved content metadata for enterprise [{}]'.format(self.enterprise_customer.name),
            'Exporting content metadata item with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Exporting content metadata item with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item creation with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item update with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Preparing to transmit content metadata item deletion with plugin configuration '
            '[<DegreedEnterpriseCustomerConfiguration for Enterprise Veridian Dynamics>]',
            'Content metadata transmission task for integrated channel configuration [{}] took [0.0] seconds'.format(
                self.degreed
            )
        ]

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('transmit_content_metadata', '--catalog_user', 'C-3PO')
            for index, message in enumerate(expected_messages):
                assert message in log_capture.records[index].getMessage()

    @responses.activate
    def test_transmit_content_metadata_task_no_channel(self):
        """
        Test the data transmission task without any integrated channel.
        """
        user = factories.UserFactory(username='john_doe')
        factories.EnterpriseCustomerFactory(
            catalog=1,
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

        uuid = str(self.enterprise_customer.uuid)
        course_run_ids = ['course-v1:edX+DemoX+Demo_Course_1', 'course-v1:edX+DemoX+Demo_Course_2']
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=uuid,
            course_run_ids=course_run_ids[:1]
        )

        with LogCapture(level=logging.INFO) as log_capture:
            call_command('transmit_content_metadata', '--catalog_user', self.user.username)

            # Because there are no active customers, the process will end early.
            assert not log_capture.records


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
    grade=LearnerExporter.GRADE_PASSING,
)

# Expected learner completion data from the mock failing certificate
CERTIFICATE_FAILING_COMPLETION = dict(
    completed='false',
    timestamp=NOW_TIMESTAMP,
    grade=LearnerExporter.GRADE_FAILING,
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
        )
        self.degreed_global_configuration = factories.DegreedGlobalConfigurationFactory(
            degreed_base_url='https://www.degreed.com/',
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
        error = 'Error: argument --api_user is required'
        with raises(CommandError, message=error):
            call_command('transmit_learner_data')

    def test_api_user_must_exist(self):
        error = 'A user with the username bob was not found.'
        with raises(CommandError, message=error):
            call_command('transmit_learner_data', '--api_user', 'bob')

    def test_enterprise_customer_not_found(self):
        faker = FakerFactory.create()
        invalid_customer_id = faker.uuid4()  # pylint: disable=no-member
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
                    "course_grade/{course}/users/?username={user}".format(course=testcase.course_id,
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


def get_expected_output(**expected_completion):
    """
    Returns the expected JSON record logged by the ``transmit_learner_data`` command.
    """
    action = 'Successfully sent completion status call for'
    if expected_completion['timestamp'] == NOW_TIMESTAMP:
        degreed_timestamp = '"{}"'.format(NOW_TIMESTAMP_FORMATTED)
    elif expected_completion['timestamp'] == PAST_TIMESTAMP:
        degreed_timestamp = '"{}"'.format(PAST_TIMESTAMP_FORMATTED)
    else:
        degreed_timestamp = 'null'
        action = 'Skipping in-progress'

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
        '"userID": "{user_id}"'
        '}}'
    )

    expected_output = [
        # SAPSF
        "Processing learners for integrated channel using configuration: "
        "[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>]",
        "Attempting to transmit serialized payload: " + sapsf_output_template.format(
            user_id='remote-user-id',
            course_id=COURSE_ID,
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
        "{} enterprise enrollment 3".format(action),
        "Learner data transmission task for integrated channel configuration "
        "[<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>] took [0.0] seconds",

        # Degreed
        "Processing learners for integrated channel using configuration: "
        "[<DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>]",
        "Attempting to transmit serialized payload: " + degreed_output_template.format(
            user_email='example@email.com',
            course_id=COURSE_ID,
            timestamp=degreed_timestamp
        ),
        "{} enterprise enrollment 2".format(action),
        "Attempting to transmit serialized payload: " + degreed_output_template.format(
            user_email='example2@email.com',
            course_id=COURSE_ID,
            timestamp=degreed_timestamp
        ),
        "{} enterprise enrollment 3".format(action),
        "Learner data transmission task for integrated channel configuration "
        "[<DegreedEnterpriseCustomerConfiguration for Enterprise Spaghetti Enterprise>] took [0.0] seconds"
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

    @responses.activate
    @ddt.data(
        # Certificate marks course completion
        (dict(), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
        (dict(), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),

        # enterprise_customer UUID gets filled in below
        (dict(enterprise_customer=None), MOCK_PASSING_CERTIFICATE, False, None, False, CERTIFICATE_PASSING_COMPLETION),
        (dict(enterprise_customer=None), MOCK_FAILING_CERTIFICATE, False, None, False, CERTIFICATE_FAILING_COMPLETION),

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
        with transmit_learner_data_context(command_kwargs, certificate, self_paced, end_date, passed) as (args, kwargs):
            with LogCapture(level=logging.INFO) as log_capture:
                expected_output = get_expected_output(**expected_completion)
                call_command('transmit_learner_data', *args, **kwargs)
                for index, message in enumerate(expected_output):
                    assert message in log_capture.records[index].getMessage()
