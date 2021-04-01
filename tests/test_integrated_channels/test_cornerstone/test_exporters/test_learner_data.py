# -*- coding: utf-8 -*-
"""
Tests for Cornerstone Learner Data exporters.
"""

import datetime
import re
import unittest

import ddt
import mock
import responses
from freezegun import freeze_time
from pytest import mark
from requests.compat import urljoin

from django.core.management import call_command
from django.utils import timezone

from enterprise.api_client import lms as lms_api
from integrated_channels.cornerstone.exporters.learner_data import CornerstoneLearnerExporter
from integrated_channels.cornerstone.models import CornerstoneLearnerDataTransmissionAudit
from integrated_channels.integrated_channel.tasks import transmit_single_learner_data
from test_utils import factories
from test_utils.fake_catalog_api import setup_course_catalog_api_client_mock


@mark.django_db
@ddt.ddt
class TestCornerstoneLearnerExporter(unittest.TestCase):
    """
    Tests of CornerstoneLearnerExporter class.
    """

    NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def setUp(self):
        self.user = factories.UserFactory()
        self.other_user = factories.UserFactory()
        self.staff_user = factories.UserFactory(is_staff=True, is_active=True)
        self.subdomain = 'fake-subdomain'
        self.session_token = 'fake-session-token'
        self.callback_url = '/services/x/content-online-content-api/v1'
        self.user_guid = "fake-guid"
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_key = 'edX+DemoX'
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            enable_audit_enrollment=True,
            enable_audit_data_reporting=True,
        )
        self.config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            active=True,
        )
        self.global_config = factories.CornerstoneGlobalConfigurationFactory(key='test_key', secret='test_secret')
        self.enterprise_course_enrollment = self._setup_enterprise_enrollment(
            self.user,
            self.course_id,
            self.course_key
        )
        course_catalog_api_client_mock = mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
        course_catalog_client = course_catalog_api_client_mock.start()
        setup_course_catalog_api_client_mock(course_catalog_client)
        self.addCleanup(course_catalog_api_client_mock.stop)
        super().setUp()

    def _setup_enterprise_enrollment(self, user, course_id, course_key):
        """
        Create enterprise enrollment for user in given course
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=self.enterprise_customer,
        )
        factories.DataSharingConsentFactory(
            username=user.username,
            course_id=course_id,
            enterprise_customer=self.enterprise_customer,
            granted=True,
        )
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
        )
        factories.CornerstoneLearnerDataTransmissionAuditFactory(
            user_id=user.id,
            session_token=self.session_token,
            callback_url=self.callback_url,
            subdomain=self.subdomain,
            course_id=course_key,
            user_guid=self.user_guid
        )
        return enterprise_course_enrollment

    @ddt.data(NOW, None)
    @freeze_time(NOW)
    def test_get_learner_data_record(self, completed_date):
        """
        The base ``get_learner_data_record`` method returns a ``LearnerDataTransmissionAudit`` with appropriate values.
        """
        exporter = CornerstoneLearnerExporter('fake-user', self.config)
        learner_data_records = exporter.get_learner_data_records(
            self.enterprise_course_enrollment,
            completed_date=completed_date,
        )
        assert learner_data_records[0].course_id == self.course_key
        assert learner_data_records[0].user_id == self.user.id
        assert learner_data_records[0].user_guid == self.user_guid
        assert learner_data_records[0].subdomain == self.subdomain
        assert learner_data_records[0].callback_url == self.callback_url
        assert learner_data_records[0].session_token == self.session_token
        assert learner_data_records[0].course_completed == (completed_date is not None)
        assert learner_data_records[0].enterprise_course_enrollment_id == self.enterprise_course_enrollment.id
        assert learner_data_records[0].completed_timestamp == (
            self.NOW if completed_date is not None else None
        )

    def test_get_learner_data_record_not_exist(self):
        """
        If learner data is not already exist, nothing is returned.
        """
        exporter = CornerstoneLearnerExporter('fake-user', self.config)
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=factories.EnterpriseCustomerUserFactory(
                user_id=self.other_user.id,
                enterprise_customer=self.enterprise_customer,
            ),
            course_id=self.course_id,
        )
        assert exporter.get_learner_data_records(enterprise_course_enrollment) is None

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.cornerstone.client.requests.post')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    def test_api_client_called_with_appropriate_payload(
        self,
        mock_get_course_details,
        mock_get_course_certificate,
        mock_post_request
    ):
        """
        Test sending of course completion data to cornerstone progress API
        """
        mock_get_course_details.return_value = {
            "course_id": self.course_key,
            "pacing": "instructor",
            "end": "2022-06-21T12:58:17.428373Z",
        }

        # Enrollment API
        responses.add(
            responses.GET,
            urljoin(
                lms_api.EnrollmentApiClient.API_BASE_URL,
                "enrollment/{username},{course_id}".format(username=self.user.username, course_id=self.course_id),
            ),
            json=dict(mode='verified')
        )

        # Certificates mock data
        certificate = dict(
            username=self.user.username,
            course_id=self.course_id,
            created_date="2019-06-21T12:58:17.428373Z",
            is_passing=True,
            grade='0.8',
        )
        mock_get_course_certificate.return_value = certificate

        call_command('transmit_learner_data', '--api_user', self.staff_user.username, '--channel', 'CSOD')
        expected_url = '{base_url}{callback_url}{completion_path}?sessionToken={session_token}'.format(
            base_url=self.config.cornerstone_base_url,
            callback_url=self.callback_url,
            completion_path=self.global_config.completion_status_api_path,
            session_token=self.session_token,
        )
        expected_payload = {
            "status": "Completed",
            "completionDate": "2019-06-21T12:58:17+00:00",
            "courseId": self.course_key,
            "successStatus": "Pass",
            "userGuid": self.user_guid,
        }
        expected_headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic dGVzdF9rZXk6dGVzdF9zZWNyZXQ=",
        }

        mock_post_request.assert_called_once()
        actual_url = mock_post_request.call_args[0][0]
        actual_payload = mock_post_request.call_args[1]['json'][0]
        actual_headers = mock_post_request.call_args[1]['headers']
        self.assertEqual(actual_url, expected_url)
        assert sorted(expected_payload.items()) == sorted(actual_payload.items())
        assert sorted(expected_headers.items()) == sorted(actual_headers.items())

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    def test_transmit_single_learner_data_performs_only_one_transmission(
        self,
        mock_get_course_details,
        mock_get_course_certificate
    ):
        """
        Test sending single user's data should only update one `CornerstoneLearnerDataTransmissionAudit` entry
        """
        course_id = 'course-v1:edX+NmX+Demo_Course_2'
        course_key = 'edX+NmX'
        self._setup_enterprise_enrollment(self.user, course_id, course_key)

        # Course API course_details response
        course_details = {
            "course_id": course_key,
            "pacing": "instructor",
            "end": "2038-06-21T12:58:17.428373Z",
        }

        mock_get_course_details.return_value = course_details

        # Enrollment API
        responses.add(
            responses.GET,
            urljoin(
                lms_api.EnrollmentApiClient.API_BASE_URL,
                "enrollment/{username},{course_id}".format(username=self.user.username, course_id=course_id),
            ),
            json=dict(mode='verified')
        )

        # Certificates mock data
        certificate = dict(
            username=self.user.username,
            course_id=self.course_id,
            created_date="2019-06-21T12:58:17.428373Z",
            is_passing=True,
            grade='0.8',
        )
        mock_get_course_certificate.return_value = certificate

        responses.add(
            responses.POST,
            re.compile(
                '{base_url}{callback}{completion_path}'.format(
                    base_url=self.config.cornerstone_base_url,
                    callback=self.callback_url,
                    completion_path=self.global_config.completion_status_api_path
                )
            ),
            json={}
        )

        transmissions = CornerstoneLearnerDataTransmissionAudit.objects.filter(user=self.user, course_completed=False)
        # assert we have two uncompleted data transmission
        self.assertEqual(transmissions.count(), 2)
        transmit_single_learner_data(self.user.username, course_id)
        # assert we have now one uncompleted data transmission
        self.assertEqual(transmissions.count(), 1)
