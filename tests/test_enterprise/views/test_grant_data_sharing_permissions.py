"""
Tests for the ``GrantDataSharingPermissions`` view of the Enterprise app.
"""

import json
import uuid
from unittest import mock

import ddt
from dateutil.parser import parse
from pytest import mark
from slumber.exceptions import HttpClientError

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.models import EnterpriseCourseEnrollment, LicensedEnterpriseCourseEnrollment
from enterprise.views import FAILED_ENROLLMENT_REASON_QUERY_PARAM, VERIFIED_MODE_UNAVAILABLE, add_reason_to_failure_url
from integrated_channels.exceptions import ClientError
from test_utils import fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    DataSharingConsentTextOverridesFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.mixins import MessagesMixin


@mark.django_db
@ddt.ddt
class TestGrantDataSharingPermissions(MessagesMixin, TestCase):
    """
    Test GrantDataSharingPermissions.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()

        LicensedEnterpriseCourseEnrollment.objects.all().delete()
        EnterpriseCourseEnrollment.objects.all().delete()
        super().setUp()

    url = reverse('grant_data_sharing_permissions')

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _assert_enterprise_linking_messages(self, response, user_is_active=True):
        """
        Verify response messages for a learner when he/she is linked with an
        enterprise depending on whether the learner has activated the linked
        account.
        """
        response_messages = self._get_messages_from_response_cookies(response)
        if user_is_active:
            # Verify that request contains the expected success message when a
            # learner with activated account is linked with an enterprise
            self.assertEqual(len(response_messages), 1)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<strong>Account created</strong> Thank you for creating an account with edX.'
            )
        else:
            # Verify that request contains the expected success message and an
            # info message when a learner with unactivated account is linked
            # with an enterprise.
            self.assertEqual(len(response_messages), 2)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<strong>Account created</strong> Thank you for creating an account with edX.'
            )
            self._assert_request_message(
                response_messages[1],
                'info',
                '<strong>Activate your account</strong> Check your inbox for an activation email. '
                'You will not be able to log back into your account until you have activated it.'
            )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @ddt.data(
        (False, True, None, 'course-v1:edX+DemoX+Demo_Course'),
        (False, False, None, 'course-v1:edX+DemoX+Demo_Course'),
        (True, False, None, 'course-v1:edX+DemoX+Demo_Course'),
        (False, True, '2013-02-05T05:00:00Z', 'course-v1:edX+DemoX+Demo_Course'),
        (False, False, '2013-02-05T05:00:00Z', 'course-v1:edX+DemoX+Demo_Course'),
        (True, False, '2013-02-05T05:00:00Z', 'course-v1:edX+DemoX+Demo_Course'),
        (False, True, None, 'edX+DemoX'),
        (False, False, None, 'edX+DemoX'),
        (True, False, None, 'edX+DemoX'),
    )
    @ddt.unpack
    def test_get_course_specific_consent(
            self,
            defer_creation,
            existing_course_enrollment,
            course_start_date,
            course_id,
            course_catalog_api_client_mock,
            enterprise_catalog_client_mock,
            *args
    ):
        content_filter = {
            'key': [
                course_id,
            ]
        }
        course_run_details = {
            'start': course_start_date,
            'title': 'Demo Course'
        }

        enterprise_catalog_client_mock.return_value.enterprise_contains_content_items.return_value = True

        mock_discovery_catalog_api_client = course_catalog_api_client_mock.return_value
        mock_discovery_catalog_api_client.get_course_id.return_value = course_id
        mock_discovery_catalog_api_client.get_course_run.return_value = course_run_details
        mock_discovery_catalog_api_client.get_course_details.return_value = course_run_details

        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        if existing_course_enrollment:
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=ecu,
                course_id=course_id
            )
        license_uuid = str(uuid.uuid4())
        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': course_id,
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
            'license_uuid': license_uuid,
        }
        if defer_creation:
            params['defer_creation'] = True
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this course, you must first consent to share your learning achievements '
            'with <b>Starfleet Academy</b>. If you decline now, you will be redirected to the previous page.'
        )
        expected_alert = (
            'To access this course and use your discount, you <b>must</b> consent to sharing your '
            'course data with Starfleet Academy. If you decline now, you will be redirected to the previous page.'
        )
        expected_course_start_date = ''
        if course_start_date:
            expected_course_start_date = parse(course_run_details['start']).strftime('%B %d, %Y')

        for key, expected_value in {
                'platform_name': 'Test platform',
                'platform_description': 'Test description',
                'tagline': "High-quality online learning opportunities from the world's best universities",
                'header_logo_alt_text': 'Test platform home page',
                'consent_request_prompt': expected_prompt,
                'requested_permissions_header': (
                    'Per the <a href="#consent-policy-dropdown-bar" '
                    'class="policy-dropdown-link background-input" id="policy-dropdown-link">'
                    'Data Sharing Policy</a>, <b>Starfleet Academy</b> would like to know about:'
                ),
                'confirmation_alert_prompt': expected_alert,
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any Test platform courses or programs that '
                    'I take on my own. I understand that I may withdraw my permission only by fully unenrolling '
                    'from any courses or programs that are sponsored by Starfleet Academy.'
                ),
                'course_id': course_id,
                'redirect_url': 'https://google.com',
                'course_specific': True,
                'defer_creation': defer_creation,
                'license_uuid': license_uuid,
                'welcome_text': 'Welcome to Test platform.',
                'sharable_items_note_header': 'Please note',
                'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
                'LMS_ROOT_URL': 'http://lms.example.com',
                'course_start_date': expected_course_start_date,
                'enterprise_customer': enterprise_customer,
                'enterprise_welcome_text': (
                    "You have left the <strong>Starfleet Academy</strong> website and are now on the "
                    "Test platform site. Starfleet Academy has partnered with Test platform to offer you "
                    "high-quality, always available learning programs to help you advance your knowledge "
                    "and career. <br/>Please note that Test platform has a different "
                    "<a href='https://www.edx.org/edx-privacy-policy' target='_blank'>Privacy Policy </a> "
                    "from Starfleet Academy."
                ),
        }.items():
            assert response.context[key] == expected_value

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_course_specific_consent_improperly_configured_course_catalog(
            self,
            course_catalog_api_client_mock,
            *args
    ):
        course_id = 'course-v1:edX+DemoX+Demo_Course'

        course_catalog_api_client_mock.side_effect = ImproperlyConfigured("There is no active CatalogIntegration.")
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        params = {
            'course_id': course_id,
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
            'defer_creation': True,
        }
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()
            self.client.get(self.url, data=params)
            assert mock_render.call_args_list[0][1]['status'] == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    def test_get_course_specific_consent_invalid_get_params(
            self,
            *args
    ):
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        params = {
            'enterprise_customer_uuid': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com',
            'defer_creation': True,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    def test_get_course_specific_consent_unauthenticated_user(
            self,
            *args
    ):
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 302
        self.assertRedirects(
            response,
            (
                '/accounts/login/?next=/enterprise/grant_data_sharing_permissions%3Fcourse_id%3Dcourse-v1'
                '%253AedX%252BDemoX%252BDemo_Course%26next%3Dhttps%253A%252F%252Fgoogle.com'
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    def test_get_course_specific_consent_bad_api_response(
            self,
            *args
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com',
        )
        assert response.status_code == 404

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_course_specific_consent_not_needed(
            self,
            course_catalog_api_client_mock,
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_catalog_api_client = course_catalog_api_client_mock.return_value
        course_catalog_api_client.is_course_in_catalog.return_value = False
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id,
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=True
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com',
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_best_mode_from_course_key')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @ddt.data(
        str(uuid.uuid4()),
        '',
    )
    def test_get_course_specific_data_sharing_consent_not_enabled(
            self,
            license_uuid,
            course_catalog_api_client_mock,
            mock_get_course_mode,
            mock_enrollment_api_client,
            *args
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=False,
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )

        course_catalog_api_client_mock.return_value.program_exists.return_value = True
        course_catalog_api_client_mock.return_value.get_course_id.return_value = course_id

        course_mode = 'verified'
        mock_get_course_mode.return_value = course_mode
        mock_enrollment_api_client.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'audit'
        }
        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': course_id,
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
            'license_uuid': license_uuid,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 302
        self.assertRedirects(response, 'https://google.com', fetch_redirect_response=False)

        # Verify the enterprise course enrollment was made with and without a license
        assert EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=ecu,
        ).exists() is True

        if license_uuid:
            assert LicensedEnterpriseCourseEnrollment.objects.filter(
                license_uuid=license_uuid,
            ).exists() is True

            mock_enrollment_api_client.return_value.enroll_user_in_course.assert_called_once_with(
                self.user.username,
                course_id,
                course_mode
            )
        else:
            assert not mock_enrollment_api_client.return_value.enroll_user_in_course.called

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.get_best_mode_from_course_key')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @ddt.data(
        str(uuid.uuid4()),
        '',
    )
    def test_get_course_specific_data_sharing_consent_enabled_audit_enrollment_exists(
            self,
            license_uuid,
            course_catalog_api_client_mock,
            mock_enrollment_api_client,
            enterprise_catalog_client_mock,
            mock_get_course_mode,
            *args
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=True
        )

        course_catalog_api_client_mock.return_value.program_exists.return_value = True
        course_catalog_api_client_mock.return_value.get_course_id.return_value = course_id

        mock_enterprise_catalog_client = enterprise_catalog_client_mock.return_value
        mock_enterprise_catalog_client.enterprise_contains_content_items.return_value = True

        course_mode = 'verified'

        mock_get_course_mode.return_value = course_mode
        mock_enrollment_api_client.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'audit'
        }
        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': course_id,
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
            'license_uuid': license_uuid,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 302
        self.assertRedirects(response, 'https://google.com', fetch_redirect_response=False)

        if license_uuid:
            # Verify the enterprise course enrollment was made with and without a license
            assert EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user=ecu,
            ).exists() is True

            assert LicensedEnterpriseCourseEnrollment.objects.filter(
                license_uuid=license_uuid,
            ).exists() is True

            mock_enrollment_api_client.return_value.enroll_user_in_course.assert_called_once_with(
                self.user.username,
                course_id,
                course_mode
            )
        else:
            assert not mock_enrollment_api_client.return_value.enroll_user_in_course.called
            assert not mock_enrollment_api_client.return_value.get_course_enrollment.called

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_course_specific_data_sharing_consent_not_enabled_exception_handling(
            self,
            course_catalog_api_client_mock,
            mock_enrollment_api_client,
            *args
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=False,
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enterprise_enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id,
        )

        course_catalog_api_client_mock.return_value.program_exists.return_value = True
        course_catalog_api_client_mock.return_value.get_course_id.return_value = course_id

        course_mode = 'verified'
        mock_enrollment_api_client.return_value.get_course_modes.return_value = [{'slug': course_mode}]
        mock_enrollment_api_client.return_value.enroll_user_in_course.side_effect = ClientError('error occurred')
        mock_enrollment_api_client.return_value.get_course_enrollment.return_value = None

        license_uuid = str(uuid.uuid4())
        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': course_id,
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
            'license_uuid': license_uuid,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 302
        self.assertRedirects(response, 'https://facebook.com', fetch_redirect_response=False)

        assert LicensedEnterpriseCourseEnrollment.objects.filter(
            enterprise_course_enrollment=enterprise_enrollment,
            license_uuid=license_uuid,
        ).exists() is False

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_best_mode_from_course_key')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.reverse')
    @ddt.data(
        (True, True, '/successful_enrollment', 'course-v1:edX+DemoX+Demo_Course', str(uuid.uuid4())),
        (True, False, '/failure_url?failure_reason=dsc_denied', 'course-v1:edX+DemoX+Demo_Course', str(uuid.uuid4())),
        (False, True, '/successful_enrollment', 'course-v1:edX+DemoX+Demo_Course', str(uuid.uuid4())),
        (False, False, '/failure_url?failure_reason=dsc_denied', 'course-v1:edX+DemoX+Demo_Course', str(uuid.uuid4())),
        (True, True, '/successful_enrollment', 'edX+DemoX', str(uuid.uuid4())),
        (True, False, '/failure_url?failure_reason=dsc_denied', 'edX+DemoX', str(uuid.uuid4())),
        (False, True, '/successful_enrollment', 'edX+DemoX', str(uuid.uuid4())),
        (False, False, '/failure_url?failure_reason=dsc_denied', 'edX+DemoX', str(uuid.uuid4())),
        (True, True, '/successful_enrollment', 'course-v1:edX+DemoX+Demo_Course', ''),
        (True, False, '/failure_url?failure_reason=dsc_denied', 'course-v1:edX+DemoX+Demo_Course', ''),
        (False, True, '/successful_enrollment', 'course-v1:edX+DemoX+Demo_Course', ''),
        (False, False, '/failure_url?failure_reason=dsc_denied', 'course-v1:edX+DemoX+Demo_Course', ''),
        (True, True, '/successful_enrollment', 'edX+DemoX', ''),
        (True, False, '/failure_url?failure_reason=dsc_denied', 'edX+DemoX', ''),
        (False, True, '/successful_enrollment', 'edX+DemoX', ''),
        (False, False, '/failure_url?failure_reason=dsc_denied', 'edX+DemoX', ''),
    )
    @ddt.unpack
    def test_post_course_specific_consent(
            self,
            defer_creation,
            consent_provided,
            expected_redirect_url,
            course_id,
            license_uuid,
            reverse_mock,
            course_catalog_api_client_mock,
            enterprise_catalog_client_mock,
            mock_get_course_mode,
            mock_enrollment_api_client,
            *args
    ):
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        # Data sharing consent record needs to exist to check if they've already consented before
        # Granted being false means they haven't enrolled in the course yet
        dsc = DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=False
        )

        course_catalog_api_client_mock.return_value.program_exists.return_value = True
        course_catalog_api_client_mock.return_value.get_course_id.return_value = 'edX+DemoX'

        mock_enterprise_catalog_client = enterprise_catalog_client_mock.return_value
        mock_enterprise_catalog_client.enterprise_contains_content_items.return_value = True
        mock_enrollment_api_client.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'audit'
        }

        reverse_mock.return_value = '/dashboard'
        course_mode = 'verified'
        mock_get_course_mode.return_value = course_mode
        post_data = {
            'enterprise_customer_uuid': enterprise_customer.uuid,
            'course_id': course_id,
            'redirect_url': '/successful_enrollment',
            'failure_url': '/failure_url',
        }
        if defer_creation:
            post_data['defer_creation'] = True
        if consent_provided:
            post_data['data_sharing_consent'] = consent_provided
        if license_uuid:
            post_data['license_uuid'] = license_uuid

        resp = self.client.post(self.url, post_data)

        assert resp.url.endswith(expected_redirect_url)
        assert resp.status_code == 302

        # we'll only create an enrollment record if (1) creation is not deferred, (2) the learner gave consent without
        # having previously consented (3) we provide a license_uuid, and (4) we provide a course _run_ id
        if not defer_creation and consent_provided and course_id.endswith('Demo_Course'):
            dsc.refresh_from_db()
            assert dsc.granted is True

            assert EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user=ecu,
                course_id=course_id,
            ).exists() is True

            if license_uuid:
                assert LicensedEnterpriseCourseEnrollment.objects.filter(
                    license_uuid=license_uuid,
                ).exists() is True
                mock_enrollment_api_client.return_value.enroll_user_in_course.assert_called_once_with(
                    self.user.username,
                    course_id,
                    course_mode
                )
            else:
                assert not mock_enrollment_api_client.return_value.enroll_user_in_course.called

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.reverse')
    def test_retrying_post_consent_when_previously_consented(
            self,
            reverse_mock,
            course_catalog_api_client_mock,
            enterprise_catalog_client_mock,
            mock_enrollment_api_client,
            *args
    ):
        defer_creation = False
        consent_provided = True
        expected_redirect_url = 'successful_enrollment'
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        license_uuid = str(uuid.uuid4())
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        content_filter = {
            'key': [
                course_id,
            ]
        }
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=True
        )

        course_catalog_api_client_mock.return_value.program_exists.return_value = True
        course_catalog_api_client_mock.return_value.get_course_id.return_value = 'edX+DemoX'

        mock_enterprise_catalog_client = enterprise_catalog_client_mock.return_value
        mock_enterprise_catalog_client.enterprise_contains_content_items.return_value = True

        reverse_mock.return_value = '/dashboard'
        post_data = {
            'enterprise_customer_uuid': enterprise_customer.uuid,
            'course_id': course_id,
            'redirect_url': '/successful_enrollment',
            'failure_url': '/failure_url',
        }
        if defer_creation:
            post_data['defer_creation'] = True
        if consent_provided:
            post_data['data_sharing_consent'] = consent_provided
        if license_uuid:
            post_data['license_uuid'] = license_uuid

        resp = self.client.post(self.url, post_data)

        assert resp.url.endswith(expected_redirect_url)
        assert resp.status_code == 302

        assert not mock_enrollment_api_client.return_value.get_course_modes.called
        assert not mock_enrollment_api_client.return_value.enroll_user_in_course.called

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_no_user(
            self,
            reverse_mock,
            *args
    ):
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'redirect_url': '/successful_enrollment',
            },
        )
        assert resp.status_code == 302
        self.assertRedirects(
            resp,
            '/accounts/login/?next=/enterprise/grant_data_sharing_permissions',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_bad_api_response(
            self,
            reverse_mock,
            *args
    ):
        self._login()
        course_id = 'course-v1:does+not+exist'
        data_sharing_consent = True
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        dsc = DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=False,
        )
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'data_sharing_consent': data_sharing_consent,
                'redirect_url': '/successful_enrollment',
                'enterprise_customer_uuid': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            },
        )
        assert resp.status_code == 404
        dsc.refresh_from_db()
        assert dsc.granted is False

    def test_add_reason_to_failure_url(self):
        base_failure_url = 'https://example.com/?enrollment_failed=true'
        failure_reason = 'something weird happened'

        actual_url = add_reason_to_failure_url(base_failure_url, failure_reason)
        expected_url = (
            'https://example.com/?enrollment_failed=true&'
            '{reason_param}=something+weird+happened'.format(
                reason_param=FAILED_ENROLLMENT_REASON_QUERY_PARAM,
            )
        )
        self.assertEqual(actual_url, expected_url)

    @mock.patch('enterprise.views.reverse', return_value='/dashboard')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.get_best_mode_from_course_key')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @ddt.data(True, False)
    def test_get_dsc_verified_mode_unavailable(
        self,
        is_post,
        mock_course_catalog_api_client,
        mock_enrollment_api_client,
        mock_enterprise_catalog_client,
        mock_get_course_mode,
        *args,
    ):
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        license_uuid = str(uuid.uuid4())

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter={'key': [course_id]},
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=not is_post,
        )

        mock_course_catalog_api_client.return_value.program_exists.return_value = True
        mock_course_catalog_api_client.return_value.get_course_id.return_value = course_id

        enterprise_catalog_client = mock_enterprise_catalog_client.return_value
        enterprise_catalog_client.enterprise_contains_content_items.return_value = True

        course_mode = 'verified'
        mock_get_course_mode.return_value = course_mode

        mock_get_enrollment = mock_enrollment_api_client.return_value.get_course_enrollment
        mock_get_enrollment.return_value = None

        mock_enroll_user = mock_enrollment_api_client.return_value.enroll_user_in_course
        client_error_content = json.dumps(
            {'message': VERIFIED_MODE_UNAVAILABLE.enrollment_client_error}
        ).encode()
        mock_enroll_user.side_effect = HttpClientError(content=client_error_content)

        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': course_id,
            'next': 'https://success.url',
            'redirect_url': 'https://success.url',
            'failure_url': 'https://failure.url',
            'license_uuid': license_uuid,
            'data_sharing_consent': True,
        }
        if is_post:
            response = self.client.post(self.url, data=params)
        else:
            response = self.client.get(self.url, data=params)

        assert response.status_code == 302
        self.assertRedirects(
            response,
            'https://failure.url?failure_reason={}'.format(VERIFIED_MODE_UNAVAILABLE.failure_reason_message),
            fetch_redirect_response=False,
        )

        assert EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=ecu,
            course_id=course_id,
        ).exists() is False

        assert LicensedEnterpriseCourseEnrollment.objects.filter(
            license_uuid=license_uuid,
        ).exists() is False


@mark.django_db
@ddt.ddt
class TestProgramDataSharingPermissions(TestCase):
    """
    Test the user-facing program consent view
    """

    url = reverse('grant_data_sharing_permissions')

    def setUp(self):
        self.user = UserFactory.create(username='john', is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        get_dsc = mock.patch('enterprise.views.get_data_sharing_consent')
        self.get_data_sharing_consent = get_dsc.start()
        self.addCleanup(get_dsc.stop)
        course_catalog_api_client = mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
        self.course_catalog_api_client = course_catalog_api_client.start()
        self.addCleanup(course_catalog_api_client.stop)
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )
        self.valid_get_params = {
            'enterprise_customer_uuid': self.enterprise_customer.uuid,
            'next': 'https://google.com/',
            'failure_url': 'https://facebook.com/',
            'program_uuid': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        }
        self.valid_post_params = {
            'enterprise_customer_uuid': self.enterprise_customer.uuid,
            'redirect_url': 'https://google.com/',
            'failure_url': 'https://facebook.com/',
            'program_uuid': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            'data_sharing_consent': 'true',
        }
        super().setUp()

    def _assert_get_returns_404_with_mock(self, url, get_params):
        """
        Mock the render method, run a GET, and assert it returns 404.
        """
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()
            self.client.get(url, get_params)
            assert mock_render.call_args_list[0][1]['status'] == 404

    def _assert_post_returns_404_with_mock(self, url, get_params):
        """
        Mock the render method, run a POST, and assert it returns 404.
        """
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()
            self.client.post(url, get_params)
            assert mock_render.call_args_list[0][1]['status'] == 404

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    @ddt.data(
        'next',
        'failure_url',
        'program_uuid',
    )
    def test_get_program_consent_missing_parameter(self, missing_parameter):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_get_params = self.valid_get_params.copy()
        valid_get_params.pop(missing_parameter)
        self._login()
        self._assert_get_returns_404_with_mock(self.url, valid_get_params)

    def test_get_program_consent_missing_parameter_enterprise_customer(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_get_params = self.valid_get_params.copy()
        valid_get_params.pop('enterprise_customer_uuid')
        self._login()
        response = self.client.get(self.url, valid_get_params)
        assert response.status_code == 404

    def test_get_consent_program_does_not_exist(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = False
        self._login()
        self._assert_get_returns_404_with_mock(self.url, self.valid_get_params)

    def test_get_program_consent_no_ec(self):
        self.get_data_sharing_consent.return_value = None
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.get(self.url, self.valid_get_params)
        assert response.status_code == 302

    def test_get_program_consent_not_required(self):
        self.get_data_sharing_consent.return_value.consent_required.return_value = False
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.get(self.url, self.valid_get_params)
        assert response.status_code == 302

    @ddt.data(
        'redirect_url',
        'failure_url',
        'program_uuid',
    )
    def test_post_program_consent_missing_parameter(self, missing_parameter):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_post_params = self.valid_post_params.copy()
        valid_post_params.pop(missing_parameter)
        self._login()
        self._assert_post_returns_404_with_mock(self.url, valid_post_params)

    def test_post_program_consent_missing_parameter_enterprise_customer(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_post_params = self.valid_post_params.copy()
        valid_post_params.pop('enterprise_customer_uuid')
        self._login()
        response = self.client.post(self.url, valid_post_params)
        assert response.status_code == 404

    def test_post_consent_program_does_not_exist(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = False
        self._login()
        self._assert_post_returns_404_with_mock(self.url, self.valid_post_params)

    def test_post_program_consent_no_ec(self):
        self.get_data_sharing_consent.return_value = None
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        self._assert_post_returns_404_with_mock(self.url, self.valid_post_params)

    def test_post_program_consent_not_required(self):
        self.get_data_sharing_consent.return_value.consent_required.return_value = False
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.post(self.url, self.valid_post_params)
        assert response.status_code == 302

    def test_post_program_consent(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.post(self.url, self.valid_post_params, follow=False)
        consent_record.save.assert_called_once()
        self.assertRedirects(response, 'https://google.com/', fetch_redirect_response=False)

    def test_post_program_consent_not_provided(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_post_params.copy()
        params.pop('data_sharing_consent')
        response = self.client.post(self.url, params, follow=False)
        # No need to update the consent record if consent not provided
        assert consent_record.save.called is False
        expected_failure_url = 'https://facebook.com/?failure_reason=dsc_denied'
        self.assertRedirects(response, expected_failure_url, fetch_redirect_response=False)

    def test_post_program_consent_deferred(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_post_params.copy()
        params['defer_creation'] = 'True'
        response = self.client.post(self.url, params, follow=False)
        consent_record.save.assert_not_called()
        self.assertRedirects(response, 'https://google.com/', fetch_redirect_response=False)

    @ddt.data(False, True)
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    def test_get_program_consent(self, defer_creation, mock_render):  # pylint: disable=unused-argument
        self.get_data_sharing_consent.return_value.consent_required.return_value = True
        enterprise_customer = self.get_data_sharing_consent.return_value.enterprise_customer
        enterprise_customer.name = 'Starfleet Academy'
        enterprise_customer.get_data_sharing_consent_text_overrides.return_value = None
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_get_params.copy()
        if defer_creation:
            params.update({'defer_creation': True})
        response = self.client.get(self.url, params)
        assert response.status_code == 200

        expected_prompt = (
            'To access this program, you must first consent to share your learning achievements '
            'with <b>Starfleet Academy</b>. If you decline now, you will be redirected to the previous page.'
        )
        expected_alert = (
            'To access this program and use your discount, you <b>must</b> consent to sharing your '
            'program data with Starfleet Academy. If you decline now, you will be redirected to the previous page.'
        )

        for key, value in {
                "platform_name": "Test platform",
                "platform_description": "Test description",
                "consent_request_prompt": expected_prompt,
                "requested_permissions_header": (
                    'Per the <a href="#consent-policy-dropdown-bar" '
                    'class="policy-dropdown-link background-input" id="policy-dropdown-link">'
                    'Data Sharing Policy</a>, <b>Starfleet Academy</b> would like to know about:'
                ),
                'confirmation_alert_prompt': expected_alert,
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any Test platform courses or programs that '
                    'I take on my own. I understand that I may withdraw my permission only by fully unenrolling '
                    'from any courses or programs that are sponsored by Starfleet Academy.'
                ),
                "program_uuid": params.get('program_uuid'),
                "redirect_url": "https://google.com/",
                "failure_url": "https://facebook.com/",
                "program_specific": True,
                "defer_creation": defer_creation,
                "welcome_text": "Welcome to Test platform.",
                'sharable_items_note_header': 'Please note',
                "enterprise_customer": enterprise_customer,
                'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
                'enterprise_welcome_text': (
                    "You have left the <strong>Starfleet Academy</strong> website and are now on the "
                    "Test platform site. Starfleet Academy has partnered with Test platform to offer you "
                    "high-quality, always available learning programs to help you advance your knowledge "
                    "and career. <br/>Please note that Test platform has a different "
                    "<a href='https://www.edx.org/edx-privacy-policy' target='_blank'>Privacy Policy </a> "
                    "from Starfleet Academy."
                ),
        }.items():
            assert response.context[key] == value


@mark.django_db
@ddt.ddt
class TestGrantDataSharingPermissionsWithDB(TestCase):
    """
    Test GrantDataSharingPermissions when content is fetched from database.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.url = reverse('grant_data_sharing_permissions')
        self.platform_name = 'Test platform'
        self.course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.program_uuid = '25c10a26-0b00-0000-bd06-7813546c29eb'
        self.course_details = {
            'name': 'edX Demo Course',
        }
        self.course_run_details = {
            'start': '2013-02-05T05:00:00Z',
            'title': 'Demo Course'
        }
        self.next_url = 'https://google.com'
        self.failure_url = 'https://facebook.com'
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )
        self.left_sidebar_text = """
        <p class="partnered-text">Welcome to {platform_name}</p>
        <p class="partnered-text"><b>{enterprise_customer_name}</b> has partnered with {platform_name}
        to offer you high-quality learning opportunities from the world\'s best universities.</p>
        """
        self.top_paragraph = """
        <h2 class="consent-title">Consent to share your data</h2>
        <p>To access this {item}, you must first consent to share your learning achievements with
        <b>{enterprise_customer_name}</b></p>
        <p>{enterprise_customer_name} would like to know about:</p>
        <p><ul><li>your enrollment in this course</li><li>your learning progress</li>
        <li>course completion</li></ul></p>
        """
        self.agreement_text = """
        I agree to allow {platform_name} to share data about my enrollment, completion and performance
        in all {platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}.
        """
        self.confirmation_modal_text = """
        In order to start this {item} and use your discount, you must consent
        to share your {item} data with {enterprise_customer_name}.
        """

        self.dsc_page = DataSharingConsentTextOverridesFactory(
            enterprise_customer=self.enterprise_customer,
            left_sidebar_text=self.left_sidebar_text,
            top_paragraph=self.top_paragraph,
            agreement_text=self.agreement_text,
            continue_text='Continue',
            abort_text='Decline and go back',
            policy_dropdown_header='Data Sharing Policy',
            policy_paragraph='Policy paragraph',
            confirmation_modal_header='Are you sure you want to decline?',
            confirmation_modal_text=self.confirmation_modal_text,
            modal_affirm_decline_text='I decline',
            modal_abort_decline_text='View the data sharing policy',
        )
        super().setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _make_paragraphs(self, item):
        """
        Returns text to be used paragraphs of data sharing consent page
        """
        left_sidebar_text = (
            self.left_sidebar_text
        ).format(
            enterprise_customer_name=self.enterprise_customer.name,
            platform_name=self.platform_name,
        )
        top_paragraph = (
            self.top_paragraph
        ).format(
            enterprise_customer_name=self.enterprise_customer.name,
            item=item,
        )
        agreement_text = (
            self.agreement_text
        ).format(
            enterprise_customer_name=self.enterprise_customer.name,
            platform_name=self.platform_name,
        )
        confirmation_modal_text = (
            self.confirmation_modal_text
        ).format(
            enterprise_customer_name=self.enterprise_customer.name,
            item=item,
        )
        return left_sidebar_text, top_paragraph, agreement_text, confirmation_modal_text

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @ddt.data(
        (False, True, True),
        (False, False, True),
        (True, False, True),
        (False, True, False),
        (False, False, False),
        (True, False, False),
    )
    @ddt.unpack
    def test_db_data_sharing_consent_page_data(
            self,
            defer_creation,
            existing_course_enrollment,
            view_for_course,
            get_data_sharing_consent_mock,
            course_catalog_api_client_view_mock,
            *args
    ):
        get_data_sharing_consent_mock.return_value.consent_required.return_value = True
        get_data_sharing_consent_mock.return_value.enterprise_customer = self.enterprise_customer
        course_catalog_api_client_view_mock.return_value.get_course_run.return_value = self.course_run_details
        item = 'course' if view_for_course else 'program'
        self._login()
        if existing_course_enrollment:
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=self.ecu,
                course_id=self.course_id
            )
        params = {
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
            'next': self.next_url,
            'failure_url': self.failure_url
        }
        if view_for_course:
            params.update({'course_id': self.course_id})
        else:
            params.update({'program_uuid': self.program_uuid})
        if defer_creation:
            params['defer_creation'] = True
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        left_sidebar_text, top_paragraph, agreement_text, confirmation_modal_text = self._make_paragraphs(item)
        expected_context = {
            'platform_name': self.platform_name,
            'platform_description': 'Test description',
            'enterprise_customer': self.enterprise_customer,
            'left_sidebar_text': left_sidebar_text,
            'top_paragraph': top_paragraph,
            'agreement_text': agreement_text,
            'continue_text': 'Continue',
            'abort_text': 'Decline and go back',
            'policy_dropdown_header': 'Data Sharing Policy',
            'policy_paragraph': 'Policy paragraph',
            'confirmation_modal_header': 'Are you sure you want to decline?',
            'confirmation_alert_prompt': confirmation_modal_text,
            'confirmation_modal_affirm_decline_text': 'I decline',
            'confirmation_modal_abort_decline_text': 'View the data sharing policy',
            'redirect_url': self.next_url,
            'defer_creation': defer_creation,
        }

        if view_for_course:
            expected_context.update({
                'course_id': self.course_id,
                'course_specific': True,
            })
        else:
            expected_context.update({
                'program_uuid': self.program_uuid,
                'program_specific': True,
            })

        for key, value in expected_context.items():
            assert response.context[key] == value

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @ddt.data(True, False)
    def test_db_data_sharing_consent_page_preview_mode_non_staff(
            self,
            view_for_course,
            *args
    ):
        self.user.is_staff = False
        self.user.save()
        self._login()
        params = {
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
            'next': self.next_url,
            'failure_url': self.failure_url,
            'preview_mode': 'true'
        }
        if view_for_course:
            params.update({'course_id': self.course_id})
        else:
            params.update({'program_uuid': self.program_uuid})
        response = self.client.get(self.url, data=params)
        assert response.status_code == 403

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @ddt.data(True, False)
    def test_db_data_sharing_consent_page_preview_mode_staff(
            self,
            view_for_course,
            *args
    ):
        self._login()
        params = {
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
            'next': self.next_url,
            'failure_url': self.failure_url,
            'preview_mode': 'true'
        }
        if view_for_course:
            params.update({'course_id': self.course_id})
        else:
            params.update({'program_uuid': self.program_uuid})
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        item = 'course' if view_for_course else 'program'
        left_sidebar_text, top_paragraph, agreement_text, confirmation_modal_text = self._make_paragraphs(item)
        expected_context = {
            'platform_name': self.platform_name,
            'platform_description': 'Test description',
            'enterprise_customer': self.enterprise_customer,
            'left_sidebar_text': left_sidebar_text,
            'top_paragraph': top_paragraph,
            'agreement_text': agreement_text,
            'continue_text': 'Continue',
            'abort_text': 'Decline and go back',
            'policy_dropdown_header': 'Data Sharing Policy',
            'policy_paragraph': 'Policy paragraph',
            'confirmation_modal_header': 'Are you sure you want to decline?',
            'confirmation_alert_prompt': confirmation_modal_text,
            'confirmation_modal_affirm_decline_text': 'I decline',
            'confirmation_modal_abort_decline_text': 'View the data sharing policy',
            'redirect_url': self.next_url,
        }

        if view_for_course:
            expected_context.update({
                'course_id': self.course_id,
                'course_specific': True,
            })
        else:
            expected_context.update({
                'program_uuid': self.program_uuid,
                'program_specific': True,
            })

        for key, value in expected_context.items():
            assert response.context[key] == value
