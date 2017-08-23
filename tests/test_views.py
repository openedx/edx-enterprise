"""
Module tests user-facing views of the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import ddt
import mock
from dateutil.parser import parse
from faker import Factory as FakerFactory
from pytest import mark
from requests.exceptions import HTTPError

from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from enterprise.utils import NotConnectedToOpenEdX
from enterprise.views import LMS_COURSEWARE_URL, LMS_DASHBOARD_URL, LMS_START_PREMIUM_COURSE_FLOW_URL, HttpClientError
# pylint: disable=import-error,wrong-import-order
from six.moves.urllib.parse import urlencode
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_catalog_api import FAKE_COURSE, FAKE_COURSE_RUN, setup_course_catalog_api_client_mock
from test_utils.fake_ecommerce_api import setup_post_order_to_ecommerce
from test_utils.mixins import MessagesMixin


def fake_render(request, template, context):  # pylint: disable=unused-argument
    """
    Switch the request to use a template that does not depend on edx-platform.
    """
    return render(request, 'enterprise/emails/user_notification.html', context=context)


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
        super(TestGrantDataSharingPermissions, self).setUp()

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

    def test_get_no_patches(self):
        """
        Test that we get the right exception when nothing is patched.
        """
        client = Client()
        with self.assertRaises(NotConnectedToOpenEdX):
            client.get(self.url)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @ddt.data(
        (False, False, True),
        (False, True, False),
        (True, True, False),
    )
    @ddt.unpack
    def test_get_course_specific_consent(
            self,
            enrollment_deferred,
            supply_customer_uuid,
            existing_course_enrollment,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
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
        if existing_course_enrollment:
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=ecu,
                course_id=course_id
            )
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com'
        }
        if enrollment_deferred:
            params['enrollment_deferred'] = True
        if supply_customer_uuid:
            params['enterprise_id'] = str(enterprise_customer.uuid)
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this course, you must first consent to share your learning achievements '
            'with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this course and use your discount, <b>you must</b> consent to share your '
            'course data with Starfleet Academy.'
        )

        for key, value in {
                "platform_name": "My Platform",
                "consent_request_prompt": expected_prompt,
                "requested_permissions_header": (
                    'Per the <a href="#consent-policy-dropdown-bar" '
                    'class="policy-dropdown-link background-input failure-link" id="policy-dropdown-link">'
                    'Data Sharing Policy</a>, <b>Starfleet Academy</b> would like to know about:'
                ),
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': '',
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any My Platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses that are sponsored by Starfleet Academy.'
                ),
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "redirect_url": "https://google.com",
                "enterprise_customer_name": ecu.enterprise_customer.name,
                "course_specific": True,
                "enrollment_deferred": enrollment_deferred,
                "welcome_text": "Welcome to My Platform.",
                'sharable_items_note_header': 'Please note',
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @ddt.data(
        (False, False),
        (True, True),
    )
    @ddt.unpack
    def test_get_course_specific_consent_ec_requires_account_level(
            self,
            enrollment_deferred,
            supply_customer_uuid,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            require_account_level_consent=True,
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
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com'
        }
        if enrollment_deferred:
            params['enrollment_deferred'] = True
        if supply_customer_uuid:
            params['enterprise_id'] = str(enterprise_customer.uuid)
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this and other courses sponsored by <b>Starfleet Academy</b>, and to '
            'use the discounts available to you, you must first consent to share your '
            'learning achievements with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this course and use your discount, <b>you must</b> consent to share your '
            'course data with Starfleet Academy.'
        )
        for key, value in {
                "platform_name": "My Platform",
                "consent_request_prompt": expected_prompt,
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': '',
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any My Platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses that are sponsored by Starfleet Academy.'
                ),
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "redirect_url": "https://google.com",
                "enterprise_customer_name": ecu.enterprise_customer.name,
                "course_specific": True,
                "enrollment_deferred": enrollment_deferred,
                "policy_link_template": "",
                "sharable_items_note_header": "Please note",
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_invalid_params(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
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
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com',
            'enrollment_deferred': True,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_unauthenticated_user(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
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
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_bad_api_response(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.side_effect = HttpClientError
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_not_needed(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id,
            consent_granted=True,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    @ddt.data(
        (True, True, '/successful_enrollment'),
        (False, True, '/successful_enrollment'),
        (True, False, '/failure_url'),
        (False, False, '/failure_url'),
    )
    @ddt.unpack
    def test_post_course_specific_consent(
            self,
            enrollment_deferred,
            consent_provided,
            expected_redirect_url,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
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
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        reverse_mock.return_value = '/dashboard'
        post_data = {
            'course_id': course_id,
            'redirect_url': '/successful_enrollment',
            'failure_url': '/failure_url',
        }
        if enrollment_deferred:
            post_data['enrollment_deferred'] = True
        if consent_provided:
            post_data['data_sharing_consent'] = consent_provided

        resp = self.client.post(self.url, post_data)

        assert resp.url.endswith(expected_redirect_url)  # pylint: disable=no-member
        assert resp.status_code == 302
        enrollment.refresh_from_db()
        if not enrollment_deferred:
            assert enrollment.consent_granted is consent_provided

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_no_user(
            self,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
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
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'redirect_url': '/successful_enrollment'
            },
        )
        assert resp.status_code == 302
        self.assertRedirects(
            resp,
            '/accounts/login/?next=/enterprise/grant_data_sharing_permissions',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_bad_api_response(
            self,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
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
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        client = course_api_client_mock.return_value
        client.get_course_details.side_effect = HttpClientError
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'data_sharing_consent': data_sharing_consent,
                'redirect_url': '/successful_enrollment'
            },
        )
        assert resp.status_code == 404
        enrollment.refresh_from_db()
        assert enrollment.consent_granted is None


class TestPushLearnerDataToIntegratedChannel(TestCase):
    """
    Test PushLearnerDataToIntegratedChannel.
    """

    url = reverse('push_learner_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass


class TestPushCatalogDataToIntegratedChannel(TestCase):
    """
    Test PushCatalogDataToIntegratedChannel.
    """

    url = reverse('push_catalog_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass


@mark.django_db
@ddt.ddt
class TestCourseEnrollmentView(MessagesMixin, TestCase):
    """
    Test CourseEnrollmentView.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.demo_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.dummy_demo_course_modes = [
            {
                "slug": "professional",
                "name": "Professional Track",
                "min_price": 100,
                "sku": "sku-professional",
            },
            {
                "slug": "audit",
                "name": "Audit Track",
                "min_price": 0,
                "sku": "sku-audit",
            },
        ]
        super(TestCourseEnrollmentView, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _setup_enrollment_client(self, client_mock):
        """
        Sets up the Enrollment API client
        """
        client = client_mock.return_value
        client.get_course_modes.return_value = self.dummy_demo_course_modes
        client.get_course_enrollment.return_value = None

    def _setup_ecommerce_client(self, client_mock, total=50):
        """
        Sets up the Ecommerce API client
        """
        dummy_price_details_mock = mock.MagicMock()
        dummy_price_details_mock.return_value = {
            'total_incl_tax': total,
        }
        price_details_mock = mock.MagicMock()
        method_name = 'baskets.calculate.get'
        attrs = {method_name: dummy_price_details_mock}
        price_details_mock.configure_mock(**attrs)
        client_mock.return_value = price_details_mock

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id, drop_existing_session=False)

    def _check_expected_enrollment_page(self, response, expected_context):
        """
        Check the response was successful, and contains the expected content.
        """
        fake_organization = FAKE_COURSE['owners'][0]
        default_context = {
            'platform_name': 'edX',
            'page_title': 'Confirm your course',
            'course_title': FAKE_COURSE_RUN['title'],
            'course_short_description': FAKE_COURSE_RUN['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(FAKE_COURSE_RUN['start']).strftime('%B %d, %Y'),
            'course_image_uri': FAKE_COURSE_RUN['image']['src'],
            'enterprise_welcome_text': (
                '<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to '
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_effort': '5-6 hours per week',
            'level_text': 'Level',
            'effort_text': 'Effort',
            'organization_logo': fake_organization['logo_image_url'],
            'organization_name': fake_organization['name'],
            'course_level_type': 'Type 1',
            'close_modal_button_text': 'Close',
        }
        default_context.update(expected_context)
        assert response.status_code == 200
        for key, value in default_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$100",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes,
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.messages.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(True, False)
    def test_get_course_enrollment_page_consent_declined(
            self,
            consent_granted,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock_1,
            configuration_helpers_mock_2,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test consent declined message is rendered.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        configuration_helpers_mock_1.get_value.side_effect = [
            settings.ENTERPRISE_SUPPORT_URL,
            settings.PLATFORM_NAME
        ]
        configuration_helpers_mock_2.get_value.return_value = 'foo'
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id
        )
        __ = EnterpriseCourseEnrollmentFactory(
            course_id=self.demo_course_id,
            consent_granted=consent_granted,
            enterprise_customer_user=enterprise_customer_user
        )
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        self._login()
        response = self.client.get(enterprise_landing_page_url)

        messages = self._get_messages_from_response_cookies(response)
        if consent_granted:
            assert not messages
        else:
            assert messages
            self._assert_request_message(
                messages[0],
                'warning',
                (
                    '<strong>We could not enroll you in <em>{course_name}</em>.</strong> '
                    '<span>If you have questions or concerns about sharing your data, please '
                    'contact your learning manager at {enterprise_customer_name}, or contact '
                    '<a href="{enterprise_support_link}" target="_blank">{platform_name} support</a>.</span>'
                ).format(
                    course_name=FAKE_COURSE_RUN['title'],
                    enterprise_customer_name=enterprise_customer.name,
                    enterprise_support_link=settings.ENTERPRISE_SUPPORT_URL,
                    platform_name=settings.PLATFORM_NAME,
                )
            )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_edge_case_formatting(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': 1},
            course_overrides={'owners': [{'name': 'Test Organization', 'logo_image_url': 'https://fake.org/fake.png'}]}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$30.10",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes,
            'course_effort': '1 hour per week',
            'organization_name': 'Test Organization',
            'organization_logo': 'https://fake.org/fake.png'
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_no_effort_no_owners(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': None},
            course_overrides={'owners': []}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$30.10",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes,
            'course_effort': '',
            'organization_name': '',
            'organization_logo': ''
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_audit_enabled(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                'mode': 'professional',
                'title': 'Professional Track',
                'original_price': '$100',
                'min_price': 100,
                'sku': 'sku-professional',
                'final_price': '$50',
                'description': 'Earn a verified certificate!',
                'premium': True,
            },
            {
                'mode': 'audit',
                'title': 'Audit Track',
                'original_price': 'FREE',
                'min_price': 0,
                'sku': 'sku-audit',
                'final_price': 'FREE',
                'description': 'Not eligible for a certificate; does not count toward a MicroMasters',
                'premium': False,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes[0:1],
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_no_start_date(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the context of the enterprise course enrollment page has
        empty course start date if course details has no start date.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock, course_run_overrides={'start': None})
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Confirm your course',
            'course_start_date': '',
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_non_existing_course(
            self,
            registry_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        or non existing course.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        course_client = catalog_api_client_mock.return_value
        course_client.get_course_and_course_run.return_value = (None, None)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_error_in_getting_course(
            self,
            registry_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of error while
        getting the course details from CourseApiClient.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        course_client = catalog_api_client_mock.return_value
        course_client.get_course_and_course_run.side_effect = HttpClientError
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_with_course_mode_error(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.side_effect = HttpClientError

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_for_invalid_ec_uuid(
            self,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=['some-fake-enterprise-customer-uuid', self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_inactive_user(
            self,
            registry_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to login screen to sign in with an
        enterprise-linked SSO.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        expected_redirect_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2Fcourse%2Fcourse-v1'
            '%253AedX%252BDemoX%252BDemo_Course%2Fenroll%2F%3Ftpa_hint%3D{provider_id}'.format(
                enterprise_customer_uuid=enterprise_customer.uuid,
                provider_id=provider_id,
            )
        )
        self.assertRedirects(response, expected_redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_landing_page_for_enrolled_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the user will be redirected to the course home page when
        the user is already enrolled.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = {"course_details": {"course_id": course_id}}
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        self.assertRedirects(
            response,
            'http://localhost:8000/courses/{course_id}/courseware'.format(course_id=course_id),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(
        ('audit', 'http://localhost:8000/courses/course-v1:edX+DemoX+Demo_Course/courseware', False),
        ('audit', 'http://localhost:8000/courses/course-v1:edX+DemoX+Demo_Course/courseware', True),
        ('professional', 'http://localhost:8000/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/', False),
        ('professional', 'http://localhost:8000/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/', True),
    )
    @ddt.unpack
    def test_post_course_specific_enrollment_view(
            self,
            enrollment_mode,
            expected_redirect_url,
            enterprise_enrollment_exists,
            registry_mock,
            is_consent_required_mock,  # pylint: disable=invalid-name
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            ecommerce_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = False
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        setup_post_order_to_ecommerce(ecommerce_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        if enterprise_enrollment_exists:
            EnterpriseCourseEnrollmentFactory(
                course_id=course_id,
                enterprise_customer_user__enterprise_customer=enterprise_customer,
                enterprise_customer_user__user_id=self.user.id
            )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': enrollment_mode})

        assert response.status_code == 302
        self.assertRedirects(
            response,
            expected_redirect_url,
            fetch_redirect_response=False
        )
        if enrollment_mode == 'audit':
            enrollment_client.enroll_user_in_course.assert_not_called()

    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_ecommerce_api_error(
            self,
            registry_mock,
            is_consent_required_mock,  # pylint: disable=invalid-name
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            ecommerce_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        is_consent_required_mock.return_value = False
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        ecommerce_api_client_mock.side_effect = HTTPError
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        provider_id = FakerFactory.create().slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'audit'})

        assert response.status_code == 302
        self.assertRedirects(
            response,
            course_enrollment_page_url,
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_consent_needed(
            self,
            registry_mock,
            is_consent_required_mock,  # pylint: disable=invalid-name
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = True
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_id = enterprise_customer.uuid
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_id, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'audit'})

        assert response.status_code == 302

        expected_url_format = '/enterprise/grant_data_sharing_permissions?{}'
        consent_enrollment_url = '/enterprise/handle_consent_enrollment/{}/course/{}/?{}'.format(
            enterprise_id, course_id, urlencode({'course_mode': 'audit'})
        )
        expected_failure_url = reverse(
            'enterprise_course_enrollment_page', args=[enterprise_customer.uuid, course_id]
        )
        self.assertRedirects(
            response,
            expected_url_format.format(
                urlencode(
                    {
                        'next': consent_enrollment_url,
                        'failure_url': expected_failure_url,
                        'enterprise_id': enterprise_id,
                        'course_id': course_id,
                    }
                )
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_incompatible_mode(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_enrollment_client(enrollment_api_client_mock)

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                'mode': 'professional',
                'title': 'Professional Track',
                'original_price': '$100',
                'min_price': 100,
                'sku': 'sku-professional',
                'final_price': '$50',
                'description': 'Earn a verified certificate!',
                'premium': True,
            },
            {
                'mode': 'audit',
                'title': 'Audit Track',
                'original_price': 'FREE',
                'min_price': 0,
                'sku': 'sku-audit',
                'final_price': 'FREE',
                'description': 'Not eligible for a certificate; does not count toward a MicroMasters',
                'premium': False,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes[0:1],
        }

        self._login()
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'fakemode'})
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_premium_mode(
            self,
            registry_mock,
            is_consent_required_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = False
        configuration_helpers_mock.get_value.return_value = 'edX'
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'professional'})

        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://localhost:8000/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_ecommerce_error(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        # Set up Ecommerce API client that returns an error
        broken_price_details_mock = mock.MagicMock()
        method_name = 'baskets.calculate.get'
        attrs = {method_name + '.side_effect': HttpClientError()}
        broken_price_details_mock.configure_mock(**attrs)
        ecommerce_api_client_mock.return_value = broken_price_details_mock

        # Set up course catalog API client
        setup_course_catalog_api_client_mock(course_catalog_client_mock)

        configuration_helpers_mock.get_value.return_value = 'edX'

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        # Get landing page
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$100",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes,
            'page_title': 'Confirm your course',
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_get_course_enrollment_page_creates_enterprise_customer_user(
            self,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument

        # Set up course catalog API client
        setup_course_catalog_api_client_mock(course_catalog_client_mock)

        configuration_helpers_mock.get_value.return_value = 'edX'

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        def ensure_enterprise_customer_user_exists(*args, **kwargs):
            """
            Ensure that the enterprise customer user exists when the commerce API client is called
            """
            assert EnterpriseCustomerUser.objects.all().count() == 1
            return mock.DEFAULT
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        ecommerce_api_client_mock.side_effect = ensure_enterprise_customer_user_exists

        # Ensure that we've started with no EnterpriseCustomerUsers
        assert EnterpriseCustomerUser.objects.all().count() == 0

        # Get landing page
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$50",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': course_modes,
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)


@mark.django_db
@ddt.ddt
class TestHandleConsentEnrollmentView(TestCase):
    """
    Test HandleConsentEnrollment.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.demo_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.dummy_demo_course_modes = [
            {
                "slug": "professional",
                "name": "Professional Track",
                "min_price": 100,
                "sku": "sku-audit",
            },
            {
                "slug": "audit",
                "name": "Audit Track",
                "min_price": 0,
                "sku": "sku-audit",
            },
        ]
        super(TestHandleConsentEnrollmentView, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id, drop_existing_session=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_without_course_mode(
            self,
            registry_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to LMS dashboard in case there is
        no parameter `course_mode` in the request querystring.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = reverse(
            'enterprise_handle_consent_enrollment',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_DASHBOARD_URL
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_404(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user gets HTTP 404 response if there is no enterprise in
        database against the provided enterprise UUID or if enrollment API
        client is unable to get course modes for the provided course id.
        """
        course_id = self.demo_course_id
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.side_effect = HttpClientError
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_no_enterprise_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user gets HTTP 404 response if the user is not linked to
        the enterprise with the provided enterprise UUID or if enrollment API
        client is unable to get course modes for the provided course id.
        """
        course_id = self.demo_course_id
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.get_enterprise_customer_user')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_invalid_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            get_ec_user_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to LMS dashboard in case the provided
        course mode does not exist.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        mocked_enterprise_customer_user = get_ec_user_mock.return_value
        mocked_enterprise_customer_user.return_value = enterprise_customer_user
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'some-invalid-course-mode'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_DASHBOARD_URL
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_audit_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            ecommerce_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to course in case the provided
        course mode is audit track.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        setup_post_order_to_ecommerce(ecommerce_api_client_mock)
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'audit'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_COURSEWARE_URL.format(course_id=course_id)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

        self.assertTrue(EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__enterprise_customer=enterprise_customer,
            enterprise_customer_user__user_id=enterprise_customer_user.user_id,
            course_id=course_id
        ).exists())

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_ecommerce_api_error(
            self,
            registry_mock,
            enrollment_api_client_mock,
            ecommerce_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to course in case the provided
        course mode is audit track.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        ecommerce_api_client_mock.side_effect = HTTPError
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'audit'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        self.assertRedirects(response, course_enrollment_page_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_professional_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to course in case the provided
        course mode is audit track.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

        self.assertTrue(EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__enterprise_customer=enterprise_customer,
            enterprise_customer_user__user_id=enterprise_customer_user.user_id,
            course_id=course_id
        ).exists())
