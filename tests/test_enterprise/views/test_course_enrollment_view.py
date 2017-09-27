# -*- coding: utf-8 -*-
"""
Tests for the ``CourseEnrollmentView`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from dateutil.parser import parse
from faker import Factory as FakerFactory
from pytest import mark
from slumber.exceptions import HttpClientError

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from six.moves.urllib.parse import urlencode  # pylint: disable=import-error
from test_utils import fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_catalog_api import FAKE_COURSE, FAKE_COURSE_RUN, setup_course_catalog_api_client_mock
from test_utils.mixins import MessagesMixin


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
            'platform_name': 'Test platform',
            'platform_description': 'Test description',
            'tagline': "High-quality online learning opportunities from the world's best universities",
            'header_logo_alt_text': "Test platform home page",
            'page_title': 'Confirm your course',
            'course_title': FAKE_COURSE_RUN['title'],
            'course_short_description': FAKE_COURSE_RUN['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(FAKE_COURSE_RUN['start']).strftime('%B %d, %Y'),
            'course_image_uri': FAKE_COURSE_RUN['image']['src'],
            'enterprise_welcome_text': (
                '<strong>Starfleet Academy</strong> has partnered with <strong>Test platform</strong> to '
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
            'discount_text': 'Discount provided by <strong>Starfleet Academy</strong>',
            'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
            'LMS_ROOT_URL': 'http://localhost:8000',
        }
        default_context.update(expected_context)
        assert response.status_code == 200
        for key, value in default_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.ProgramDataExtender')
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
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
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
    @mock.patch('enterprise.views.ProgramDataExtender')
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
            *args
    ):  # pylint: disable=unused-argument
        """
        Test consent declined message is rendered.
        """
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
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
    @mock.patch('enterprise.views.ProgramDataExtender')
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
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': 1},
            course_overrides={'owners': [{'name': 'Test Organization', 'logo_image_url': 'https://fake.org/fake.png'}]}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_empty_fields(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(
            course_catalog_client_mock,
            course_run_overrides={'min_effort': None, 'max_effort': None, 'image': None},
            course_overrides={'owners': []}
        )
        self._setup_ecommerce_client(ecommerce_api_client_mock, 30.1)
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
            'organization_logo': '',
            'course_image_uri': '',
        }

        self._login()
        response = self.client.get(enterprise_landing_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.ProgramDataExtender')
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
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
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
    @mock.patch('enterprise.views.ProgramDataExtender')
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
            *args
    ):  # pylint: disable=unused-argument
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
            'platform_name': 'Test platform',
            'platform_description': 'Test description',
            'page_title': 'Confirm your course',
            'course_start_date': '',
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_non_existing_course(
            self,
            registry_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        or non existing course.
        """
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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_error_in_getting_course(
            self,
            registry_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of error while
        getting the course details from CourseApiClient.
        """
        course_client = catalog_api_client_mock.return_value
        course_client.get_course_and_course_run.side_effect = ImproperlyConfigured
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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_with_course_mode_error(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        setup_course_catalog_api_client_mock(catalog_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = {}

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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_for_invalid_ec_uuid(
            self,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_inactive_user(
            self,
            registry_mock,
            *args
    ):  # pylint: disable=unused-argument
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
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
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
                provider_id=provider_id,
            ),
            'new_enterprise_login%3Dyes'
        )
        assert response.status_code == 302
        assert expected_base_url in response.url
        for fragment in expected_fragments:
            assert fragment in response.url

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_landing_page_for_enrolled_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the user will be redirected to the course home page when
        the user is already enrolled.
        """
        course_id = self.demo_course_id
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
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.consent_required')
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
            consent_required_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            ecommerce_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        consent_required_mock.return_value = False
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
            enrollment_client.enroll_user_in_course.assert_called_once_with(self.user.username, course_id, 'audit')

    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.consent_required')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_consent_needed(
            self,
            registry_mock,
            consent_required_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        consent_required_mock.return_value = True
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
            *args
    ):  # pylint: disable=unused-argument
        setup_course_catalog_api_client_mock(course_catalog_client_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
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
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.consent_required')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_premium_mode(
            self,
            registry_mock,
            consent_required_mock,
            enrollment_api_client_mock,
            catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        consent_required_mock.return_value = False
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
    @mock.patch('enterprise.views.ProgramDataExtender')
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
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_get_course_enrollment_page_creates_enterprise_customer_user(
            self,
            ecommerce_api_client_mock,
            enrollment_api_client_mock,
            course_catalog_client_mock,
            *args
    ):  # pylint: disable=unused-argument

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
