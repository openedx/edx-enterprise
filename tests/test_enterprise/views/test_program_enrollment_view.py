"""
Tests for the ``ProgramEnrollmentView`` view of the Enterprise app.
"""

import copy
from unittest import mock
from urllib.parse import urlencode
from uuid import uuid4

import ddt
from faker import Factory as FakerFactory
from pytest import mark

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.utils import NotConnectedToOpenEdX
from test_utils import fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_catalog_api import FAKE_PROGRAM_RESPONSE3, setup_course_catalog_api_client_mock
from test_utils.mixins import EmbargoAPIMixin, MessagesMixin


@mark.django_db
@ddt.ddt
class TestProgramEnrollmentView(EmbargoAPIMixin, MessagesMixin, TestCase):
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
        self.demo_course_1 = FAKE_PROGRAM_RESPONSE3['courses'][0]
        self.demo_course_2 = FAKE_PROGRAM_RESPONSE3['courses'][1]
        self.demo_course_id1 = FAKE_PROGRAM_RESPONSE3['courses'][0]['key']
        self.demo_course_id2 = FAKE_PROGRAM_RESPONSE3['courses'][1]['key']
        self.demo_course_ids = [self.demo_course_id1, self.demo_course_id2]
        self.dummy_program_uuid = FAKE_PROGRAM_RESPONSE3['uuid']
        self.dummy_program = FAKE_PROGRAM_RESPONSE3
        super().setUp()

    def _login(self):
        """
        Log the user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _assert_get_returns_404_with_mock(self, url):
        """
        Mock the render method, run a GET, and assert it returns 404.
        """
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()
            self.client.get(url)
            assert mock_render.call_args_list[0][1]['status'] == 404

    def _setup_course_catalog_client(self, client_mock):
        """
        Sets up the Course Catalog API client.
        """
        client = client_mock.return_value
        client.get_program_course_keys.return_value = self.demo_course_ids
        client.get_program_by_uuid.return_value = self.dummy_program

    def _setup_program_data_extender(self, extender_mock, course_overrides=None):
        """
        Sets up the `ProgramDataExtender` mock, a utility from the edx-platform.
        """
        # TODO: Update this mock when we upstream the additional program context from `get_program_details`.
        dummy_program_extended = copy.deepcopy(self.dummy_program)
        dummy_course_extended_1 = copy.deepcopy(self.demo_course_1)
        dummy_course_extended_2 = copy.deepcopy(self.demo_course_2)
        if course_overrides:
            dummy_course_extended_1.update(course_overrides)
            dummy_course_extended_2.update(course_overrides)
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
        registry_mock.get.return_value.configure_mock(provider_id=provider_id)

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
            assert response.context[key] == value

    def test_get_no_patches(self):
        """
        An error is raised when not connected to Open edX for the Program Enrollment View.
        """
        with self.assertRaises(NotConnectedToOpenEdX):
            self._login()
            self.client.get(
                reverse(
                    'enterprise_program_enrollment_page',
                    args=[EnterpriseCustomerFactory().uuid, self.dummy_program_uuid])
            )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The Enterprise Program landing page is rendered appropriately given some context.
        """
        self._setup_embargo_api(embargo_api_mock)
        self._setup_program_data_extender(program_data_extender_mock)
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        expected_context = {
            'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
            'LMS_ROOT_URL': 'http://lms.example.com',
            'enterprise_customer': enterprise_customer,
            'platform_name': 'Test platform',
            'program_type_logo': 'http://localhost:18381/media/media/program_types/logo_images/'
                                 'professional-certificate.medium.png',
            'platform_description': 'Test description',
            'program_type_description_header': 'What is an Test platform Professional Certificate?',
            'platform_description_header': 'What is Test platform?',
            'tagline': "High-quality online learning opportunities from the world's best universities",
            'header_logo_alt_text': 'Test platform home page',
            'organization_name': 'Authoring Organization',
            'organization_logo': 'images/logo_image_url.jpg',
            'program_type': 'Professional Certificate',
            'program_type_description': 'Designed by industry leaders and top universities to enhance '
                                        'professional skills, Professional Certificates develop the '
                                        'proficiency and expertise that employers are looking for with '
                                        'specialized training and professional education.',
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
                    'course_title': 'edX Demonstration Course',
                    'course_short_description': 'This course demonstrates many features of the edX platform.',
                    'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                    'course_image_uri': 'http://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type'
                                        '@asset+block@images_course_image.jpg',
                    'course_level_type': 'Type 1',
                    'weeks_to_complete': '10 weeks',
                    'course_effort': '5-6 hours per week',
                    'staff': [
                        {
                            'uuid': '51df1077-1b8d-4f86-8305-8adbc82b72e9',
                            'given_name': 'Anant',
                            'family_name': 'Agarwal',
                            'bio': "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                            'profile_image_url': 'https://www.edx.org/sites/default/files/executive/photo/'
                                                 'anant-agarwal.jpg',
                            'slug': 'anant-agarwal',
                            'position': {
                                'title': 'CEO',
                                'organization_name': 'edX'
                            },
                            'profile_image': {},
                            'works': [],
                            'urls': {
                                'twitter': None,
                                'facebook': None,
                                'blog': None
                            },
                            'email': None
                        }
                    ],
                    'expected_learning_items': [
                        'XBlocks',
                        'Peer Assessment',
                    ],
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
                    'course_title': 'edX Demonstration Course',
                    'course_short_description': 'This course demonstrates many features of the edX platform.',
                    'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                    'course_image_uri': 'http://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type'
                                        '@asset+block@images_course_image.jpg',
                    'course_level_type': 'Type 1',
                    'course_effort': '5-6 hours per week',
                    'weeks_to_complete': '10 weeks',
                    'staff': [
                        {
                            'uuid': '51df1077-1b8d-4f86-8305-8adbc82b72e9',
                            'given_name': 'Anant',
                            'family_name': 'Agarwal',
                            'bio': "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                            'profile_image_url': 'https://www.edx.org/sites/default/files/executive/photo/'
                                                 'anant-agarwal.jpg',
                            'slug': 'anant-agarwal',
                            'position': {
                                'title': 'CEO',
                                'organization_name': 'edX'
                            },
                            'profile_image': {},
                            'works': [],
                            'urls': {
                                'twitter': None,
                                'facebook': None,
                                'blog': None
                            },
                            'email': None
                        }
                    ],
                    'expected_learning_items': [
                        'XBlocks',
                        'Peer Assessment',
                    ],
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
            'course_count_text': '2 Courses',
            'item_bullet_points': [
                'Credit- and Certificate-eligible',
                'Self-paced; courses can be taken in any order',
            ],
            'enrolled_in_course_and_paid_text': 'enrolled',
            'enrolled_in_course_and_unpaid_text': 'already enrolled, must pay for certificate',
            'expected_learning_items_text': "What you'll learn",
            'expected_learning_items': [
                "Blocks",
                "XBlocks",
                "Peer Assessment"
            ],
            'expected_learning_items_show_count': 2,
            'corporate_endorsements_text': 'Real Career Impact',
            'corporate_endorsements': [
                {
                    "corporation_name": "Bob's Company",
                    "statement": "",
                    "image": {
                        "src": "http://evonexus.org/wp-content/uploads/2016/01/IBM-logo-1024x576.jpg",
                        "description": None,
                        "height": None,
                        "width": None,
                    },
                    "individual_endorsements": [
                        {
                            "endorser": {
                                "uuid": "789aa881-e44b-4675-9377-fa103c12bbfc",
                                "given_name": "Bob",
                                "family_name": "the Builder",
                                "bio": "Working hard on a daily basis!",
                                "profile_image_url": None,
                                "slug": "bob-the-builder",
                                "position": {
                                    "title": "Engineer",
                                    "organization_name": "Bob's Company",
                                    "organization_id": 1
                                },
                                "profile_image": {},
                                "works": [],
                                "urls": {
                                    "facebook": None,
                                    "twitter": None,
                                    "blog": None,
                                },
                                "email": None
                            },
                            "quote": "Life is hard for us engineers. Period."
                        }
                    ]
                }
            ],
            'corporate_endorsements_show_count': 1,
            'see_more_text': 'See More',
            'see_less_text': 'See Less',
            'confirm_button_text': 'Confirm Program',
            'summary_header': 'Program Summary',
            'price_text': 'Price',
            'length_text': 'Length',
            'length_info_text': '4-6 weeks per course',
            'effort_text': 'Effort',
            'effort_info_text': '5-10 hours per week, per course',
            'program_not_eligible_for_one_click_purchase_text': 'Program not eligible for one-click purchase.',
            'level_text': 'Level',
            'course_full_description_text': 'About This Course',
            'staff_text': 'Course Staff',
            'close_modal_button_text': 'Close',
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
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_enrolled_in_program(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The Enterprise Program landing page is rendered appropriately given that the user is enrolled in the program.
        """
        self._setup_embargo_api(embargo_api_mock)
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        program_data_extender_mock.return_value.extend.return_value['courses'][0]['course_runs'][0].update({
            "is_enrolled": True,
            "upgrade_url": None,
        })
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        expected_context = {
            'page_title': 'Confirm your enrollment',
            'purchase_text': 'Purchase all unenrolled courses for',
            'courses': [
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course',
                    "uuid": "a312ec52-74ef-434b-b848-f110eb90b672",
                    "title": "edX Demonstration Course",
                    'course_title': 'edX Demonstration Course',
                    'course_short_description': 'This course demonstrates many features of the edX platform.',
                    'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                    'course_image_uri': 'http://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type'
                                        '@asset+block@images_course_image.jpg',
                    'course_level_type': 'Type 1',
                    'course_effort': '5-6 hours per week',
                    'weeks_to_complete': '10 weeks',
                    'staff': [
                        {
                            'uuid': '51df1077-1b8d-4f86-8305-8adbc82b72e9',
                            'given_name': 'Anant',
                            'family_name': 'Agarwal',
                            'bio': "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                            'profile_image_url': 'https://www.edx.org/sites/default/files/executive/photo/'
                                                 'anant-agarwal.jpg',
                            'slug': 'anant-agarwal',
                            'position': {
                                'title': 'CEO',
                                'organization_name': 'edX'
                            },
                            'profile_image': {},
                            'works': [],
                            'urls': {
                                'twitter': None,
                                'facebook': None,
                                'blog': None
                            },
                            'email': None
                        }
                    ],
                    'expected_learning_items': [
                        'XBlocks',
                        'Peer Assessment',
                    ],
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
                    'course_title': 'edX Demonstration Course',
                    'course_short_description': 'This course demonstrates many features of the edX platform.',
                    'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                    'course_image_uri': 'http://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type'
                                        '@asset+block@images_course_image.jpg',
                    'course_level_type': 'Type 1',
                    'course_effort': '5-6 hours per week',
                    'weeks_to_complete': '10 weeks',
                    'staff': [
                        {
                            'uuid': '51df1077-1b8d-4f86-8305-8adbc82b72e9',
                            'given_name': 'Anant',
                            'family_name': 'Agarwal',
                            'bio': "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                            'profile_image_url': 'https://www.edx.org/sites/default/files/executive/photo/'
                                                 'anant-agarwal.jpg',
                            'slug': 'anant-agarwal',
                            'position': {
                                'title': 'CEO',
                                'organization_name': 'edX'
                            },
                            'profile_image': {},
                            'works': [],
                            'urls': {
                                'twitter': None,
                                'facebook': None,
                                'blog': None
                            },
                            'email': None
                        }
                    ],
                    'expected_learning_items': [
                        'XBlocks',
                        'Peer Assessment',
                    ],
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
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    @ddt.data(True, False)
    def test_get_program_enrollment_page_consent_message(
            self,
            consent_granted,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The DSC-declined message is rendered if DSC is not given.
        """
        self._setup_embargo_api(embargo_api_mock)
        self._setup_program_data_extender(program_data_extender_mock)
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
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
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_no_price_info_found_message(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The message about no price information found is rendered if the program extender fails to get price info.
        """
        self._setup_embargo_api(embargo_api_mock)
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        program_data_extender_mock.return_value.extend.return_value['discount_data'] = {}
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
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
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    @ddt.data(True, False)
    def test_get_program_enrollment_page_program_unenrollable(
            self,
            enrollable,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The message about the program being unenrollable is displayed.
        """
        self._setup_embargo_api(embargo_api_mock)
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock).return_value
        program_data_extender_mock.extend.return_value['is_learner_eligible_for_one_click_purchase'] = enrollable
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        messages = self._get_messages_from_response_cookies(response)
        if enrollable:
            assert not messages
        else:
            assert messages
            self._assert_request_message(
                messages[0],
                'info',
                (
                    '<strong>Something happened.</strong> '
                    '<span>This program is not currently open to new learners. '
                    'Please start over and select a different program.</span>'
                )
            )

    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_program_enrollment_page_for_non_existing_program(
            self,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The user will see the HTTP 404 (Not Found) page in case of an invalid or non existing program.
        """
        self._setup_embargo_api(embargo_api_mock)
        course_catalog_api_client_mock.return_value.get_program_by_uuid.return_value = None
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        self._assert_get_returns_404_with_mock(program_enrollment_page_url)

    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_program_enrollment_page_for_non_existing_program_type(
            self,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The user will see the HTTP 404 (Not Found) page in case of an invalid or non existing program type.
        """
        self._setup_embargo_api(embargo_api_mock)
        course_catalog_api_client_mock.return_value.get_program_type_by_slug.return_value = None
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        self._assert_get_returns_404_with_mock(program_enrollment_page_url)

    def test_get_program_enrollment_page_for_invalid_ec_uuid(self):
        """
        The user will see the HTTP 404 (Not Found) page in case of an invalid enterprise customer UUID.
        """
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[uuid4(), self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_for_nonexisting_ec(self, *args):
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
    ):
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
        expected_base_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2F'
            'program%2F{program_uuid}%2Fenroll%2F'
        ).format(
            enterprise_customer_uuid=enterprise_customer.uuid,
            program_uuid=self.dummy_program_uuid
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

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_get_program_enrollment_page_for_certificate_eligible_user(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            *args
    ):
        """
        The user will be redirected to the program's dashboard when already certificate-eligible for the program.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        for course in program_data_extender_mock.return_value.extend.return_value['courses']:
            course['course_runs'][0].update({
                "is_enrolled": True,
                "upgrade_url": None,
            })
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        self.assertRedirects(
            response,
            'http://lms.example.com/dashboard/programs/{program_uuid}'.format(program_uuid=self.dummy_program_uuid),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_program_enrollment_page_with_discovery_error(
            self,
            course_catalog_api_client_mock,
            *args
    ):
        """
        We raise a 404 when there are Discovery API-related errors.
        """
        course_catalog_api_client_mock.side_effect = ImproperlyConfigured
        enterprise_customer = EnterpriseCustomerFactory()
        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        self._assert_get_returns_404_with_mock(program_enrollment_page_url)

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_post_program_enrollment_view_redirect_to_program_dashboard(
            self,
            course_catalog_api_client_mock,
            program_data_extender_mock,
            *args
    ):
        """
        The user is redirected to the program dashboard on POST if already certificate eligible for the program.
        """
        program_data_extender_mock = self._setup_program_data_extender(program_data_extender_mock)
        for course in program_data_extender_mock.return_value.extend.return_value['courses']:
            course['course_runs'][0].update({
                "is_enrolled": True,
                "upgrade_url": None,
            })
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
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
            'http://lms.example.com/dashboard/programs/52ad909b-c57d-4ff1-bab3-999813a2479b',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.get_data_sharing_consent')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_post_program_enrollment_view_redirect_to_dsc(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            get_dsc_mock,
            *args
    ):
        """
        The user is redirected to the DSC page when DSC is needed.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
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
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_post_program_enrollment_view_redirect_to_basket(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            get_dsc_mock,
            *args
    ):
        """
        The user is redirected to the basket page when something needs to be bought.
        """
        self._setup_program_data_extender(program_data_extender_mock)
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
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

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.api_client.lms.embargo_api')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.ProgramDataExtender')
    def test_embargo_restriction(
            self,
            program_data_extender_mock,
            course_catalog_api_client_mock,
            embargo_api_mock,
            *args
    ):
        """
        The Enterprise Program landing page is rendered appropriately given some context.
        """
        self._setup_embargo_api(embargo_api_mock, redirect_url=self.EMBARGO_REDIRECT_URL)
        self._setup_program_data_extender(program_data_extender_mock)
        setup_course_catalog_api_client_mock(course_catalog_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(name='Starfleet Academy')

        program_enrollment_page_url = reverse(
            'enterprise_program_enrollment_page',
            args=[enterprise_customer.uuid, self.dummy_program_uuid],
        )

        self._login()
        response = self.client.get(program_enrollment_page_url)
        assert response.status_code == 302
        self.assertRedirects(
            response,
            self.EMBARGO_REDIRECT_URL,
            fetch_redirect_response=False
        )
