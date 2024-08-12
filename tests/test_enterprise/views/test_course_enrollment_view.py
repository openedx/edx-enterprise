"""
Tests for the ``CourseEnrollmentView`` view of the Enterprise app.
"""

import datetime
from collections import OrderedDict
from unittest import mock
from urllib.parse import urlencode

import ddt
from dateutil.parser import parse
from faker import Factory as FakerFactory
from pytest import mark
from requests.exceptions import HTTPError

from django.conf import settings
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured
from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.decorators import FRESH_LOGIN_PARAMETER
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, EnterpriseEnrollmentSource
from test_utils import FAKE_UUIDS, fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_catalog_api import FAKE_COURSE, FAKE_COURSE_RUN, setup_course_catalog_api_client_mock
from test_utils.mixins import EmbargoAPIMixin, EnterpriseViewMixin, MessagesMixin


@mark.django_db
@ddt.ddt
class TestCourseEnrollmentView(EmbargoAPIMixin, EnterpriseViewMixin, MessagesMixin, TestCase):
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
        self.faker = FakerFactory.create()
        self.provider_id = self.faker.slug()  # pylint: disable=no-member
        super().setUp()

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
        client_mock.return_value.get.return_value.json.return_value = {'total_incl_tax': total}

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id)

    def _check_expected_enrollment_page(self, response, expected_context):
        """
        Check the response was successful, and contains the expected content.
        """
        fake_organization = FAKE_COURSE['owners'][0]
        default_context = {
            'platform_name': 'Test platform',
            'platform_description': 'Test description',
            'tagline': "High-quality online learning opportunities from the world's best universities",
            'header_logo_alt_text': "Test platform home page",
            'page_title': 'Confirm your course',
            'course_title': FAKE_COURSE_RUN['title'],
            'course_short_description': FAKE_COURSE_RUN['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(FAKE_COURSE_RUN['start']).strftime('%B %d, %Y'),
            'course_in_future': False,
            'course_image_uri': FAKE_COURSE_RUN['image']['src'],
            'enterprise_welcome_text': (
                "You have left the <strong>Starfleet Academy</strong> website and are now on the "
                "Test platform site. Starfleet Academy has partnered with Test platform to offer you "
                "high-quality, always available learning programs to help you advance your knowledge and career. "
                "<br/>Please note that Test platform has a different <a href='https://www.edx.org/edx-privacy-policy' "
                "target='_blank'>Privacy Policy </a> from Starfleet Academy."
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
            'discount_text': 'Discount provided by <strong>Starfleet Academy</strong>',
            'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
            'LMS_ROOT_URL': 'http://lms.example.com',
            'course_enrollable': True,
        }
        default_context.update(expected_context)
        assert response.status_code == 200
        for key, value in default_context.items():
            assert response.context[key] == value

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        future_date = datetime.datetime.utcnow() + datetime.timedelta(days=365)
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'start': future_date.isoformat() + 'Z'}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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
            'course_start_date': future_date.strftime('%B %d, %Y'),
            'course_in_future': True,
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(True, False)
    def test_hide_course_original_price_value_on_enrollment_page(
            self,
            hide_course_original_price,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            hide_course_original_price=hide_course_original_price,
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        if hide_course_original_price:
            self.assertTrue(response.context['hide_course_original_price'])
        else:
            self.assertFalse(response.context['hide_course_original_price'])

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(
        (['verified', 'professional', 'no-id-professional', 'credit', 'audit', 'honor'], ['professional', 'audit']),
        (['audit', 'professional'], ['audit', 'professional']),
        (['professional'], ['professional']),
        (['audit'], ['audit']),
    )
    @ddt.unpack
    def test_get_course_enrollment_page_with_catalog(
            self,
            enabled_course_modes,
            expected_course_modes,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            ent_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify the course modes displayed on enterprise course enrollment page.

        If enterprise course enrollment url has the querystring `catalog` then
        the modes displayed on enterprise course enrollment page will be
        filtered and ordered according to the value for the field
        "enabled_course_modes" of its related EnterpriseCustomerCatalog record.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        ent_catalog_api_client_mock.return_value.contains_content_items.return_value = True

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        catalog_uuid = FAKE_UUIDS[1]
        catalog_title = 'All Content'
        catalog_filter = {}
        # Create enterprise customer catalog record and provide desired value
        # for the field "enabled_course_modes".
        enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(
            uuid=catalog_uuid,
            title=catalog_title,
            enterprise_customer=enterprise_customer,
            content_filter=catalog_filter,
            enabled_course_modes=enabled_course_modes,
        )
        all_course_modes = {
            'audit': {
                'mode': 'audit',
                'title': 'Audit Track',
                'original_price': 'FREE',
                'min_price': 0,
                'sku': 'sku-audit',
                'final_price': 'FREE',
                'description': 'Not eligible for a certificate.',
                'premium': False,
            },
            'professional': {
                'mode': 'professional',
                'title': 'Professional Track',
                'original_price': '$100',
                'min_price': 100,
                'sku': 'sku-professional',
                'final_price': '$100',
                'description': 'Earn a verified certificate!',
                'premium': True,
            }
        }
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)

        course_enrollment_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        querystring_dict = QueryDict('', mutable=True)
        querystring_dict.update({
            'catalog': enterprise_customer_catalog.uuid
        })
        enterprise_landing_page_url = self._append_fresh_login_param(
            '{course_enrollment_url}?{querystring}'.format(
                course_enrollment_url=course_enrollment_url,
                querystring=querystring_dict.urlencode()
            )
        )

        # Set up expected context for enterprise course enrollment page
        course_modes = [
            all_course_modes[mode] for mode in expected_course_modes if mode in all_course_modes
        ]
        audit_modes = getattr(
            settings,
            'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES',
            ['audit', 'honor']
        )
        premium_course_modes = [
            course_mode for course_mode in course_modes if course_mode['mode'] not in audit_modes
        ]
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': course_modes,
            'premium_modes': premium_course_modes,
        }
        self._login()
        expected_log_messages = []
        response = self.client.get(enterprise_landing_page_url)

        self._assert_django_test_client_messages(response, expected_log_messages)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_invalid_catalog(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            catalog_api_client_views_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify course modes and messages displayed on course enrollment page.

        If enterprise course enrollment url has the querystring `catalog` and
        there is no related EnterpriseCustomerCatalog record in database then
        user will see a generic info message and no course modes will be
        displayed.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_views_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)

        course_enrollment_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        querystring_dict = QueryDict('', mutable=True)
        invalid_enterprise_catalog_uuid = self.faker.uuid4()  # pylint: disable=no-member
        querystring_dict.update({
            'catalog': invalid_enterprise_catalog_uuid
        })
        enterprise_landing_page_url = self._append_fresh_login_param(
            '{course_enrollment_url}?{querystring}'.format(
                course_enrollment_url=course_enrollment_url,
                querystring=querystring_dict.urlencode()
            )
        )
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': [],
            'premium_modes': [],
        }
        self._login()

        expected_log_messages = [
            (
                messages.ERROR,
                self._get_expected_generic_error_message('ENTCEV002', self.user),
            )
        ]
        response = self.client.get(enterprise_landing_page_url)
        self._assert_django_test_client_messages(response, expected_log_messages)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_course_enrollment_page_with_catalog_for_invalid_course_modes(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            catalog_api_client_views_mock,
            catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify course modes and messages displayed on course enrollment page.

        If enterprise course enrollment url has the querystring `catalog` and
        the course modes saved in the field "enabled_course_modes" for its
        related EnterpriseCustomerCatalog record are not available for the
        actual course then user will see a generic info message and no course
        modes will be displayed.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_views_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        catalog_api_client_mock.return_value.contains_content_items.return_value = True

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        catalog_uuid = FAKE_UUIDS[1]
        catalog_title = 'All Content'
        catalog_filter = {}
        # Create enterprise customer catalog record and provide a course mode
        # for the field "enabled_course_modes" which does not exist for the
        # actual course.
        enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(
            uuid=catalog_uuid,
            title=catalog_title,
            enterprise_customer=enterprise_customer,
            content_filter=catalog_filter,
            enabled_course_modes=['invalid-course-mode'],
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)

        course_enrollment_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        querystring_dict = QueryDict('', mutable=True)
        querystring_dict.update({
            'catalog': enterprise_customer_catalog.uuid
        })
        enterprise_landing_page_url = self._append_fresh_login_param(
            '{course_enrollment_url}?{querystring}'.format(
                course_enrollment_url=course_enrollment_url,
                querystring=querystring_dict.urlencode()
            )
        )
        expected_context = {
            'enterprise_customer': enterprise_customer,
            'course_modes': [],
            'premium_modes': [],
        }
        self._login()

        expected_log_messages = [
            (
                messages.ERROR,
                self._get_expected_generic_error_message('ENTCEV001', self.user),
            )
        ]
        response = self.client.get(enterprise_landing_page_url)
        self._assert_django_test_client_messages(response, expected_log_messages)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(True, False)
    def test_get_course_enrollment_page_consent_declined(
            self,
            consent_granted,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Test consent declined message is rendered.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id
        )
        EnterpriseCourseEnrollmentFactory(
            course_id=self.demo_course_id,
            enterprise_customer_user=enterprise_customer_user
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=self.demo_course_id,
            enterprise_customer=enterprise_customer,
            granted=consent_granted
        )
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )

        self._login()
        response = self.client.get(enterprise_landing_page_url)

        response_messages = self._get_messages_from_response_cookies(response)
        if consent_granted:
            assert not response_messages
        else:
            assert response_messages
            self._assert_request_message(
                response_messages[0],
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

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(True, False)
    def test_get_course_enrollment_page_course_unenrollable(
            self,
            enrollable,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The message indicating that the course is currently unopen to new learners is rendered.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock, course_run_overrides={
            'end': None if enrollable else '1900-10-13T13:11:01Z',
        })
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
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
        EnterpriseCourseEnrollmentFactory(
            course_id=self.demo_course_id,
            enterprise_customer_user=enterprise_customer_user
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=self.demo_course_id,
            enterprise_customer=enterprise_customer,
        )
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )

        self._login()
        response = self.client.get(enterprise_landing_page_url)

        response_messages = self._get_messages_from_response_cookies(response)
        if enrollable:
            assert not response_messages
        else:
            assert response_messages
            self._assert_request_message(
                response_messages[0],
                'info',
                (
                    '<strong>Something happened.</strong> '
                    '<span>This course is not currently open to new learners. Please start over and select a different '
                    'course.</span>'
                )
            )

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_course_unenrollable_context(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The course enrollment landing page returns context indicating that the course is unenrollable.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock, course_run_overrides={
            'end': '1900-10-13T13:11:01Z'
        })
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )

        expected_context = {'course_enrollable': False}
        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_edge_case_formatting(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': 1},
            course_overrides={'owners': [{'name': 'Test Organization', 'logo_image_url': 'https://fake.org/fake.png'}]}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_empty_fields(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': None, 'image': None},
            course_overrides={'owners': []}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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
            'organization_logo': '',
            'course_image_uri': '',
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_audit_enabled(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._setup_embargo_api(embargo_api_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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
                'description': 'Not eligible for a certificate.',
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

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_no_start_date(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify that the context of the enterprise course enrollment page has
        empty course start date if course details has no start date.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock, course_run_overrides={'start': None})
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        course_id = self.demo_course_id
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        self._setup_embargo_api(embargo_api_mock)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200
        expected_context = {
            'platform_name': 'Test platform',
            'platform_description': 'Test description',
            'page_title': 'Confirm your course',
            'course_start_date': '',
            'course_in_future': False,
        }
        for key, value in expected_context.items():
            assert response.context[key] == value

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_non_existing_course(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify that user will see generic info message in case of invalid
        or non existing course.
        """
        course_client = catalog_api_client_mock.return_value
        course_client.get_course_and_course_run.return_value = (None, None)
        course_client.get_course_id.return_value = None
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = {}
        self._setup_embargo_api(embargo_api_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200
        expected_log_messages = [
            (
                messages.ERROR,
                self._get_expected_generic_error_message('ENTCEV004', self.user),
            )
        ]
        self._assert_django_test_client_messages(response, expected_log_messages)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_error_in_getting_course(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify that user will see generic info message in case of error while
        getting the course details from CourseApiClient.
        """
        course_client = catalog_api_client_mock.return_value
        course_client.get_course_and_course_run.side_effect = ImproperlyConfigured
        course_client.get_course_id.side_effect = ImproperlyConfigured
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = {}
        self._setup_embargo_api(embargo_api_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200
        expected_log_messages = [
            (
                messages.ERROR,
                self._get_expected_generic_error_message('ENTCEV003', self.user),
            )
        ]
        self._assert_django_test_client_messages(response, expected_log_messages)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_with_course_mode_error(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify that user will see generic error message in case of invalid
        enterprise customer uuid.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = {}
        self._setup_embargo_api(embargo_api_mock)

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200

        expected_log_messages = [
            (
                messages.ERROR,
                self._get_expected_generic_error_message('ENTCEV000', self.user),
            )
        ]
        self._assert_django_test_client_messages(response, expected_log_messages)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_for_invalid_ec_uuid(
            self,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=['some-fake-enterprise-customer-uuid', self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_inactive_user(
            self,
            registry_mock,
            *args
    ):
        """
        Verify that user is redirected to login screen to sign in with an
        enterprise-linked SSO.
        """
        course_id = self.demo_course_id

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )
        response = self.client.get(enterprise_landing_page_url)

        expected_base_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2Fcourse%2Fcourse-v1'
            '%253AedX%252BDemoX%252BDemo_Course%2Fenroll%2F'
        ).format(
            enterprise_customer_uuid=enterprise_customer.uuid,
        )
        expected_fragments = (
            'tpa_hint%3D{provider_id}'.format(
                provider_id=self.provider_id,
            ),
            'new_enterprise_login%3Dyes'
        )
        assert response.status_code == 302
        assert expected_base_url in response.url
        for fragment in expected_fragments:
            assert fragment in response.url

    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_landing_page_for_enrolled_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        Verify that the user will be redirected to the course home page when
        the user is already enrolled.
        """
        course_id = self.demo_course_id
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = {"course_details": {"course_id": course_id}}
        self._setup_embargo_api(embargo_api_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )
        response = self.client.get(enterprise_landing_page_url)
        self.assertRedirects(
            response,
            'http://lms.example.com/courses/{course_id}/courseware'.format(course_id=course_id),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.views.track_enrollment')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(
        ('audit', 'http://lms.example.com/courses/course-v1:edX+DemoX+Demo_Course/courseware', False, None),
        ('audit', 'http://lms.example.com/courses/course-v1:edX+DemoX+Demo_Course/courseware', True, None),
        ('audit', 'http://lms.example.com/courses/course-v1:edX+DemoX+Demo_Course/courseware', True, 'My Cohort'),
        (
            'professional',
            'http://lms.example.com/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/',
            False,
            None
        ),
        (
            'professional',
            'http://lms.example.com/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/',
            True,
            None
        ),
    )
    @ddt.unpack
    def test_post_course_specific_enrollment_view(
            self,
            enrollment_mode,
            expected_redirect_url,
            enterprise_enrollment_exists,
            cohort_name,
            registry_mock,
            get_data_sharing_consent_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            ecommerce_api_client_mock,  # pylint: disable=unused-argument
            track_enrollment_mock,
            *args
    ):
        course_id = self.demo_course_id
        get_data_sharing_consent_mock.return_value = mock.MagicMock(consent_required=mock.MagicMock(return_value=False))
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)

        if enterprise_enrollment_exists:
            EnterpriseCourseEnrollmentFactory(
                course_id=course_id,
                enterprise_customer_user__enterprise_customer=enterprise_customer,
                enterprise_customer_user__user_id=self.user.id,
            )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )

        post_data = {
            'course_mode': enrollment_mode
        }
        if cohort_name:
            post_data['cohort'] = cohort_name

        if enrollment_mode == 'professional':
            enterprise_catalog_uuid = str(enterprise_customer.enterprise_customer_catalogs.first().uuid)
            post_data.update({
                'catalog': enterprise_catalog_uuid
            })
            expected_redirect_url += '?catalog={}'.format(enterprise_catalog_uuid)

        response = self.client.post(course_enrollment_page_url, post_data)

        if enterprise_enrollment_exists or enrollment_mode == 'professional':
            track_enrollment_mock.assert_not_called()
        else:
            track_enrollment_mock.assert_called_once_with(
                'course-landing-page-enrollment',
                self.user.id,
                course_id,
                course_enrollment_page_url,
            )

        assert response.status_code == 302
        self.assertRedirects(
            response,
            expected_redirect_url,
            fetch_redirect_response=False
        )
        if enrollment_mode == 'audit':
            enrollment_client.enroll_user_in_course.assert_called_once_with(
                self.user.username,
                course_id,
                'audit',
                cohort=cohort_name,
                enterprise_uuid=str(enterprise_customer.uuid)
            )
            # Check EnterpriseCourseEnrollment Source
            enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.get(
                enterprise_customer_user__user_id=self.user.id,
                course_id=course_id,
            )
            if not enterprise_enrollment_exists:
                assert enterprise_course_enrollment.source.slug == EnterpriseEnrollmentSource.ENROLLMENT_URL

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_consent_needed(
            self,
            registry_mock,
            get_data_sharing_consent_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):
        course_id = self.demo_course_id
        get_data_sharing_consent_mock.return_value = mock.MagicMock(consent_required=mock.MagicMock(return_value=True))
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
        enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_uuid = enterprise_customer.uuid
        self._login()
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer_uuid, course_id],
            )
        )
        response = self.client.post(
            course_enrollment_page_url,
            {'course_mode': 'audit', 'catalog': enterprise_customer_catalog.uuid}
        )

        assert response.status_code == 302

        expected_url_format = '/enterprise/grant_data_sharing_permissions?{}'
        consent_enrollment_url = '/enterprise/handle_consent_enrollment/{}/course/{}/?{}'.format(
            enterprise_customer_uuid, course_id, urlencode({
                'course_mode': 'audit',
                'catalog': enterprise_customer_catalog.uuid
            })
        )
        expected_failure_url = '{course_enrollment_url}?{query_string}'.format(
            course_enrollment_url=reverse(
                'enterprise_course_run_enrollment_page', args=[enterprise_customer.uuid, course_id]
            ),
            query_string=urlencode({FRESH_LOGIN_PARAMETER: 'yes'}),
        )
        self.assertRedirects(
            response,
            expected_url_format.format(
                urlencode(
                    {
                        'next': consent_enrollment_url,
                        'failure_url': expected_failure_url,
                        'enterprise_customer_uuid': enterprise_customer_uuid,
                        'course_id': course_id,
                    }
                )
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_consent_needed_with_catalog_querystring(
            self,
            registry_mock,
            get_data_sharing_consent_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):
        course_id = self.demo_course_id
        get_data_sharing_consent_mock.return_value = mock.MagicMock(consent_required=mock.MagicMock(return_value=True))
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
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_uuid = enterprise_customer.uuid
        self._login()
        catalog_uuid = FAKE_UUIDS[1]
        catalog_title = 'All Content'
        catalog_filter = {}
        # Create enterprise customer catalog record and provide desired value
        # for the field "enabled_course_modes".
        enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(
            uuid=catalog_uuid,
            title=catalog_title,
            enterprise_customer=enterprise_customer,
            content_filter=catalog_filter,
            enabled_course_modes=['audit', 'professional'],
        )
        course_enrollment_page_url = self._append_fresh_login_param(
            '{course_enrollment_url}?{query_string}'.format(
                course_enrollment_url=reverse(
                    'enterprise_course_run_enrollment_page', args=[enterprise_customer_uuid, course_id]
                ),
                query_string=urlencode({'catalog_uuid': enterprise_customer_catalog.uuid})
            )
        )
        response = self.client.post(
            course_enrollment_page_url,
            {'course_mode': 'audit', 'catalog': enterprise_customer_catalog.uuid}
        )
        assert response.status_code == 302

        expected_url_format = '/enterprise/grant_data_sharing_permissions?{}'
        consent_enrollment_url = '/enterprise/handle_consent_enrollment/{}/course/{}/?{}'.format(
            enterprise_customer_uuid, course_id, urlencode({
                'course_mode': 'audit',
                'catalog': enterprise_customer_catalog.uuid
            })
        )
        expected_failure_url = '{course_enrollment_url}?{query_string}'.format(
            course_enrollment_url=reverse(
                'enterprise_course_run_enrollment_page', args=[enterprise_customer.uuid, course_id]
            ),
            query_string=urlencode(OrderedDict([
                ('catalog_uuid', enterprise_customer_catalog.uuid),
                (FRESH_LOGIN_PARAMETER, 'yes'),
            ]))
        )
        self.assertRedirects(
            response,
            expected_url_format.format(
                urlencode(
                    {
                        'next': consent_enrollment_url,
                        'failure_url': expected_failure_url,
                        'enterprise_customer_uuid': enterprise_customer_uuid,
                        'course_id': course_id,
                    }
                )
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_incompatible_mode(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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
                'description': 'Not eligible for a certificate.',
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
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_premium_mode(
            self,
            registry_mock,
            get_data_sharing_consent_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):
        course_id = self.demo_course_id
        get_data_sharing_consent_mock.return_value = mock.MagicMock(consent_required=mock.MagicMock(return_value=False))
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )
        enterprise_catalog_uuid = str(enterprise_customer.enterprise_customer_catalogs.first().uuid)
        response = self.client.post(
            course_enrollment_page_url, {
                'course_mode': 'professional',
                'catalog': enterprise_catalog_uuid
            }
        )

        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://lms.example.com/verify_student/start-flow/{}/?catalog={}'.format(
                'course-v1:edX+DemoX+Demo_Course',
                enterprise_catalog_uuid
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_invite_only_courses(
            self,
            registry_mock,
            get_data_sharing_consent_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):
        course_id = self.demo_course_id
        get_data_sharing_consent_mock.return_value = mock.MagicMock(consent_required=mock.MagicMock(return_value=False))
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        enrollment_api_client_mock.return_value.get_course_details.return_value = {"invite_only": True}

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=False,
            enable_audit_enrollment=False,
            allow_enrollment_in_invite_only_courses=True,
        )
        EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, course_id],
            )
        )
        enterprise_catalog_uuid = str(enterprise_customer.enterprise_customer_catalogs.first().uuid)

        response = self.client.post(
            course_enrollment_page_url, {
                'course_mode': 'professional',
                'catalog': enterprise_catalog_uuid
            }
        )

        enrollment_api_client_mock.return_value.allow_enrollment.assert_called_with(
            self.user.email,
            course_id,
        )
        assert response.status_code == 302

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_ecommerce_error(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        # Set up Ecommerce API client that returns an error
        broken_price_details_mock = mock.MagicMock()
        broken_price_details_mock.get.side_effect = HTTPError
        ecommerce_api_client_mock.return_value = broken_price_details_mock
        self._setup_embargo_api(embargo_api_mock)

        # Set up course catalog API client
        setup_course_catalog_api_client_mock(course_catalog_client_mock)

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        # Get landing page
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
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

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    def test_get_course_enrollment_page_creates_enterprise_customer_user(
            self,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            embargo_api_mock,
            *args
    ):
        self._setup_embargo_api(embargo_api_mock)

        # Set up course catalog API client
        setup_course_catalog_api_client_mock(course_catalog_client_mock)

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
            'enterprise_course_run_enrollment_page',
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

    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.utils.Registry')
    def test_embargo_restriction(
            self,
            registry_mock,
            embargo_api_mock,
            *args
    ):
        self._setup_embargo_api(embargo_api_mock, redirect_url=self.EMBARGO_REDIRECT_URL)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._setup_registry_mock(registry_mock, self.provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=enterprise_customer)

        enterprise_landing_page_url = self._append_fresh_login_param(
            reverse(
                'enterprise_course_run_enrollment_page',
                args=[enterprise_customer.uuid, self.demo_course_id],
            )
        )

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 302
        self.assertRedirects(
            response,
            self.EMBARGO_REDIRECT_URL,
            fetch_redirect_response=False
        )
