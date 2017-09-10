# -*- coding: utf-8 -*-
"""
Tests for the ``ProgramEnrollmentView`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import copy

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from six.moves.urllib.parse import urlencode  # pylint: disable=import-error
from test_utils import fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.mixins import MessagesMixin


@mark.django_db
@ddt.ddt
class TestProgramEnrollmentView(MessagesMixin, TestCase):
    """
    ProgramEnrollmentView test cases.
    """

    def setUp(self):
        """
        Set up reusable fake data.
        """
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.demo_course_id1 = 'course-v1:edX+DemoX+Demo_Course'
        self.demo_course_1 = {
            "key": self.demo_course_id1,
            "uuid": "a312ec52-74ef-434b-b848-f110eb90b672",
            "title": "edX Demonstration Course",
            "course_runs": [
                {
                    "key": self.demo_course_id1,
                    "uuid": "a276c25f-c640-4943-98dd-6c9ad8c71bb9",
                    "title": "edX Demonstration Course",
                    "short_description": "",
                    "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                    "seats": [],
                    "start": "2016-01-01T00:00:00Z",
                    "end": "2018-01-01T00:00:00Z",
                    "enrollment_start": None,
                    "enrollment_end": None,
                    "pacing_type": "self_paced",
                    "type": None,
                    "status": "published",
                },
            ],
        }
        self.demo_course_id2 = 'course-v1:edX+DemoX+Demo_Course2'
        self.demo_course_2 = {
            "key": self.demo_course_id2,
            "uuid": "b312ec52-74ef-434b-b848-f110eb90b672",
            "title": "edX Demonstration Course 2",
            "course_runs": [
                {
                    "key": self.demo_course_id2,
                    "uuid": "b276c25f-c640-4943-98dd-6c9ad8c71bb9",
                    "title": "edX Demonstration Course 2",
                    "short_description": "",
                    "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                    "seats": [],
                    "start": "2016-01-01T00:00:00Z",
                    "end": "2018-01-01T00:00:00Z",
                    "enrollment_start": None,
                    "enrollment_end": None,
                    "pacing_type": "self_paced",
                    "type": None,
                    "status": "published",
                },
            ],
        }
        self.demo_course_ids = [
            self.demo_course_id1,
            self.demo_course_id2,
        ]
        self.dummy_program_uuid = "52ad909b-c57d-4ff1-bab3-999813a2479b"
        self.dummy_program = {
            "uuid": self.dummy_program_uuid,
            "title": "Program Title 1",
            "subtitle": "Program Subtitle 1",
            "type": "Verified Certificate",
            "status": "active",
            "marketing_slug": "marketingslug1",
            "marketing_url": "verified-certificate/marketingslug1",
            "courses": [
                self.demo_course_1,
                self.demo_course_2,
            ],
            "authoring_organizations": [
                {
                    "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
                    "key": "edX",
                    "name": "Authoring Organization",
                    "certificate_logo_image_url": 'awesome/certificate/logo/url.jpg',
                    "description": 'Such author, much authoring',
                    "homepage_url": 'homepage.com/url',
                    "logo_image_url": 'images/logo_image_url.jpg',
                    "marketing_url": 'marketing/url',
                },
            ],
            "expected_learning_items": [
                "Blocks",
                "XBlocks",
                "Peer Assessment"
            ],
            "is_program_eligible_for_one_click_purchase": True,
            "overview": "This is a test Program.",
            "weeks_to_complete_min": 4,
            "weeks_to_complete_max": 6,
            "min_hours_effort_per_week": 5,
            "max_hours_effort_per_week": 10,
            "applicable_seat_types": [
                "verified",
                "professional",
                "credit",
            ],
        }
        self.configuration_helpers_order = ['edX', 'edX', settings.ENTERPRISE_TAGLINE]
        super(TestProgramEnrollmentView, self).setUp()

    def _login(self):
        """
        Log the user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _setup_course_catalog_client(self, client_mock):
        """
        Sets up the Course Catalog API client.
        """
        client = client_mock.return_value
        client.get_program_course_keys.return_value = self.demo_course_ids
        client.get_program_by_uuid.return_value = self.dummy_program

    def _setup_program_data_extender(self, extender_mock):
        """
        Sets up the `ProgramDataExtender` mock, a utility from the edx-platform.
        """
        # TODO: Update this mock when we upstream the additional program context from `get_program_details`.
        dummy_program_extended = copy.deepcopy(self.dummy_program)
        dummy_course_extended_1 = copy.deepcopy(self.demo_course_1)
        dummy_course_extended_2 = copy.deepcopy(self.demo_course_2)
        dummy_course_extended_1['course_runs'][0].update({"is_enrolled": False, "upgrade_url": None})
        dummy_course_extended_2['course_runs'][0].update({"is_enrolled": False, "upgrade_url": None})
        dummy_program_extended.update({
            "courses": [
                dummy_course_extended_1,
                dummy_course_extended_2,
            ],
            "discount_data": {
                "currency": "USD",
                "discounted_value": 50,
                "is_discounted": True,
                "total_incl_tax": 250.0,
                "total_incl_tax_excl_discounts": 300.0,
            },
            "full_program_price": 250.0,
            "is_learner_eligible_for_one_click_purchase": True,
            "skus": [
                "sku1",
                "sku2",
            ],
            "variant": "full",
        })
        extender_mock.return_value.extend.return_value = dummy_program_extended
        return extender_mock

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object.
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id, drop_existing_session=False)

    def _setup_get_data_sharing_consent(self, client_mock, required):
        """
        Sets up the ``get_data_sharing_consent`` function mock.
        """
        client_mock.return_value.consent_required.return_value = required

    def _setup_get_base_details_mock(
            self,
            client_mock,
            program_details,
            program_enrollment_details
    ):
        """
        Sets up the ``enterprise.views.ProgramEnrollmentView.get_base_details`` function mock.
        """
        client_mock.return_value = (program_details, program_enrollment_details,)

    def _check_expected_enrollment_page(self, response, expected_context):
        """
        Check that the response was successful, and contains the expected content.
        """
        default_context = {}
        default_context.update(expected_context)
        assert response.status_code == 200
        for key, value in default_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The Enterprise Program landing page is rendered appropriately given some context.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        expected_context = {
            'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
            'enterprise_customer': enterprise_customer,
            'platform_name': 'Test platform',
            'tagline': "High-quality online learning opportunities from the world's best universities",
            'organization_name': 'Authoring Organization',
            'organization_logo': 'images/logo_image_url.jpg',
            'welcome_text': 'Welcome to Test platform.',
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>Test platform</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'page_title': 'Confirm your program enrollment',
            'program_title': 'Program Title 1',
            'program_subtitle': 'Program Subtitle 1',
            'program_overview': 'This is a test Program.',
            'program_price': '$300',
            'program_discounted_price': '$250',
            'is_discounted': True,
            'courses': [
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course',
                    "uuid": "a312ec52-74ef-434b-b848-f110eb90b672",
                    "title": "edX Demonstration Course",
                    "course_runs": [
                        {
                            "key": 'course-v1:edX+DemoX+Demo_Course',
                            "uuid": "a276c25f-c640-4943-98dd-6c9ad8c71bb9",
                            "title": "edX Demonstration Course",
                            "short_description": "",
                            "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                            "seats": [],
                            "start": "2016-01-01T00:00:00Z",
                            "end": "2018-01-01T00:00:00Z",
                            "enrollment_start": None,
                            "enrollment_end": None,
                            "pacing_type": "self_paced",
                            "type": None,
                            "status": "published",
                            "is_enrolled": False,
                            "upgrade_url": None,
                        },
                    ],
                },
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course2',
                    "uuid": "b312ec52-74ef-434b-b848-f110eb90b672",
                    "title": "edX Demonstration Course 2",
                    "course_runs": [
                        {
                            "key": 'course-v1:edX+DemoX+Demo_Course2',
                            "uuid": "b276c25f-c640-4943-98dd-6c9ad8c71bb9",
                            "title": "edX Demonstration Course 2",
                            "short_description": "",
                            "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                            "seats": [],
                            "start": "2016-01-01T00:00:00Z",
                            "end": "2018-01-01T00:00:00Z",
                            "enrollment_start": None,
                            "enrollment_end": None,
                            "pacing_type": "self_paced",
                            "type": None,
                            "status": "published",
                            "is_enrolled": False,
                            "upgrade_url": None,
                        },
                    ],
                },
            ],
            'purchase_text': 'Pursue the program for',
            'discount_provider': 'Discount provided by <strong>Starfleet Academy</strong>.',
            'course_count_text': '2 Courses',
            'item_bullet_points': [
                'Credit- and Certificate-eligible',
                'Self-paced; courses can be taken in any order',
            ],
            'enrolled_in_course_and_paid_text': 'enrolled',
            'enrolled_in_course_and_unpaid_text': 'already enrolled, must pay for certificate',
            'expected_learning_items_header': "What you'll learn",
            'expected_learning_items': [
                "Blocks",
                "XBlocks",
                "Peer Assessment"
            ],
            'view_expected_learning_items_text': 'See More',
            'hide_expected_learning_items_text': 'See Less',
            'confirm_button_text': 'Confirm Program',
            'summary_header': 'Program Summary',
            'price_text': 'Price',
            'length_text': 'Length',
            'length_info_text': '4-6 weeks per course',
            'effort_text': 'Effort',
            'effort_info_text': '5-10 hours per week, per course',
            'program_not_eligible_for_one_click_purchase_text': 'Program not eligible for one-click purchase.',
            'is_learner_eligible_for_one_click_purchase': True,
        }
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_enrolled_in_program(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The Enterprise Program landing page is rendered appropriately given that the user is enrolled in the program.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        program_data_extender_mock.return_value.extend.return_value['courses'][0]['course_runs'][0].update({
            "is_enrolled": True,
            "upgrade_url": None,
        })
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        expected_context = {
            'page_title': 'Confirm your enrollment',
            'purchase_text': 'Purchase all unenrolled courses for',
            'courses': [
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course',
                    "uuid": "a312ec52-74ef-434b-b848-f110eb90b672",
                    "title": "edX Demonstration Course",
                    "course_runs": [
                        {
                            "key": 'course-v1:edX+DemoX+Demo_Course',
                            "uuid": "a276c25f-c640-4943-98dd-6c9ad8c71bb9",
                            "title": "edX Demonstration Course",
                            "short_description": "",
                            "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                            "seats": [],
                            "start": "2016-01-01T00:00:00Z",
                            "end": "2018-01-01T00:00:00Z",
                            "enrollment_start": None,
                            "enrollment_end": None,
                            "pacing_type": "self_paced",
                            "type": None,
                            "status": "published",
                            "is_enrolled": True,
                            "upgrade_url": None,
                        },
                    ],
                },
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course2',
                    "uuid": "b312ec52-74ef-434b-b848-f110eb90b672",
                    "title": "edX Demonstration Course 2",
                    "course_runs": [
                        {
                            "key": 'course-v1:edX+DemoX+Demo_Course2',
                            "uuid": "b276c25f-c640-4943-98dd-6c9ad8c71bb9",
                            "title": "edX Demonstration Course 2",
                            "short_description": "",
                            "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                            "seats": [],
                            "start": "2016-01-01T00:00:00Z",
                            "end": "2018-01-01T00:00:00Z",
                            "enrollment_start": None,
                            "enrollment_end": None,
                            "pacing_type": "self_paced",
                            "type": None,
                            "status": "published",
                            "is_enrolled": False,
                            "upgrade_url": None,
                        },
                    ],
                },
            ],
        }
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        self._check_expected_enrollment_page(response, expected_context)

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    @ddt.data(True, False)
    def test_get_program_enrollment_page_consent_message(
            self,
            consent_granted,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The DSC-declined message is rendered if DSC is not given.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id
        )
        for dummy_course_id in self.demo_course_ids:
            DataSharingConsentFactory(
                course_id=dummy_course_id,
                granted=consent_granted,
                enterprise_customer=enterprise_customer,
                username=enterprise_customer_user.username,
            )
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        messages = self._get_messages_from_response_cookies(response)
        if consent_granted:
            assert not messages
        else:
            assert messages
            self._assert_request_message(
                messages[0],
                'warning',
                (
                    '<strong>We could not enroll you in <em>Program Title 1</em>.</strong> '
                    '<span>If you have questions or concerns about sharing your data, please '
                    'contact your learning manager at Starfleet Academy, or contact '
                    '<a href="{enterprise_support_link}" target="_blank">{platform_name} support</a>.</span>'
                ).format(
                    enterprise_support_link=settings.ENTERPRISE_SUPPORT_URL,
                    platform_name=settings.PLATFORM_NAME,
                )
            )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_no_price_info_found_message(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The message about no price information found is rendered if the program extender fails to get price info.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        program_data_extender_mock.return_value.extend.return_value['discount_data'] = {}
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        messages = self._get_messages_from_response_cookies(response)
        assert messages
        self._assert_request_message(
            messages[0],
            'warning',
            (
                '<strong>We could not gather price information for <em>Program Title 1</em>.</strong> '
                '<span>If you continue to have these issues, please contact '
                '<a href="{enterprise_support_link}" target="_blank">{platform_name} support</a>.</span>'
            ).format(
                enterprise_support_link=settings.ENTERPRISE_SUPPORT_URL,
                platform_name=settings.PLATFORM_NAME,
            )
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_not_one_click_purchasable_message(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The message about the program not being one-click purchasable is rendered if it really isn't.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        program_data_extender_mock.return_value.extend.return_value['is_learner_eligible_for_one_click_purchase'] \
            = False
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        messages = self._get_messages_from_response_cookies(response)
        assert messages
        self._assert_request_message(
            messages[0],
            'warning',
            (
                '<strong>We could not load the program titled <em>Program Title 1</em> through Starfleet Academy.'
                '</strong> <span>If you have any questions, please contact your learning manager at Starfleet Academy, '
                'or contact <a href="{enterprise_support_link}" target="_blank">{platform_name} support</a>.</span>'
            ).format(
                enterprise_support_link=settings.ENTERPRISE_SUPPORT_URL,
                platform_name=settings.PLATFORM_NAME,
            )
        )

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    def test_get_program_enrollment_page_for_non_existing_program(
            self,
            course_catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        The user will see the HTTP 404 (Not Found) page in case of an invalid or non existing program.
        """
        course_catalog_api_client_mock.return_value.get_program_by_uuid.return_value = None
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 404

    def test_get_program_enrollment_page_for_invalid_ec_uuid(self):
        """
        The user will see the HTTP 404 (Not Found) page in case of an invalid enterprise customer UUID.
        """
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=['some-fake-enterprise-customer-uuid', self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_for_nonexisting_ec(self, *args):  # pylint: disable=unused-argument
        """
        The user will see the HTTP 404 (Not Found) page in case of no matching ``EnterpriseCustomer``.
        """
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=['9f9093b0-58e9-480c-a619-5af5000507bb', self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.utils.Registry')
    def test_get_program_enrollment_page_for_inactive_user(
            self,
            registry_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        The user is redirected to the login screen to sign in with an enterprise-linked SSO when inactive.
        """
        enterprise_customer = EnterpriseCustomerFactory()
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        response = self.client.get(program_enrollment_page_url)
        expected_redirect_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2Fprogram%2F'
            '{program_uuid}%2Fenroll%2F%3Ftpa_hint%3D{provider_id}'.format(
                enterprise_customer_uuid=enterprise_customer.uuid,
                program_uuid=self.dummy_program_uuid,
                provider_id=provider_id,
            )
        )
        self.assertRedirects(response, expected_redirect_url, fetch_redirect_response=False)

    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_for_certificate_eligible_user(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The user will be redirected to the program's dashboard when already certificate-eligible for the program.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        for course in program_data_extender_mock.return_value.extend.return_value['courses']:
            course['course_runs'][0].update({
                "is_enrolled": True,
                "upgrade_url": None,
            })
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        self.assertRedirects(
            response,
            'http://localhost:8000/dashboard/programs/{program_uuid}'.format(program_uuid=self.dummy_program_uuid),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    def test_get_program_enrollment_page_with_discovery_error(
            self,
            course_catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        We raise a 404 when there are Discovery API-related errors.
        """
        course_catalog_api_client_mock.return_value.get_program_by_uuid.side_effect = ImproperlyConfigured
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    def test_post_program_enrollment_view_redirect_to_program_dashboard(
            self,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            program_data_extender_mock,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        """
        The user is redirected to the program dashboard on POST if already certificate eligible for the program.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        for course in program_data_extender_mock.return_value.extend.return_value['courses']:
            course['course_runs'][0].update({
                "is_enrolled": True,
                "upgrade_url": None,
            })
        self._setup_course_catalog_client(course_catalog_api_client_mock_1)
        self._setup_course_catalog_client(course_catalog_api_client_mock_2)
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.post(program_enrollment_page_url)
        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://localhost:8000/dashboard/programs/52ad909b-c57d-4ff1-bab3-999813a2479b',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_post_program_enrollment_view_redirect_to_dsc(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            get_dsc_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        The user is redirected to the DSC page when DSC is needed.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        self._setup_course_catalog_client(course_catalog_api_client_mock)
        self._setup_get_data_sharing_consent(get_dsc_mock, required=True)
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.post(program_enrollment_page_url)
        assert response.status_code == 302
        self.assertRedirects(
            response,
            '/enterprise/grant_data_sharing_permissions?{}'.format(
                urlencode(
                    {
                        'next': 'http://localhost:18130/basket/add/?sku=sku1&sku=sku2'
                                '&bundle=52ad909b-c57d-4ff1-bab3-999813a2479b',
                        'failure_url': program_enrollment_page_url,
                        'enterprise_customer_uuid': enterprise_customer.uuid,
                        'program_uuid': self.dummy_program_uuid,
                    }
                )
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_post_program_enrollment_view_redirect_to_basket(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            get_dsc_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        The user is redirected to the basket page when something needs to be bought.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        self._setup_course_catalog_client(course_catalog_api_client_mock)
        self._setup_get_data_sharing_consent(get_dsc_mock, required=False)
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.post(program_enrollment_page_url)
        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://localhost:18130/basket/add/?sku=sku1&sku=sku2&bundle=52ad909b-c57d-4ff1-bab3-999813a2479b',
            fetch_redirect_response=False
        )
