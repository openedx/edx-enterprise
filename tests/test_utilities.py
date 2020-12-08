# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""

import datetime
import unittest

import ddt
import mock
import pytz
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import override_settings

from enterprise import utils
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerUser,
)
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import TEST_UUID, create_items, fake_catalog_api
from test_utils.factories import (
    FAKER,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    SiteFactory,
    UserFactory,
)

DATETIME_NOW = datetime.datetime.utcnow()


def mock_get_available_idps(idps):
    """
    Mock method for get_available_idps.
    """
    def _():
        """
        mock function for get_available_idps.
        """
        idp_list = []
        for idp in idps:
            mock_idp = mock.Mock()
            mock_idp.configure_mock(provider_id=idp, name=idp)
            idp_list.append(mock_idp)
        return idp_list
    return _


@mark.django_db
@ddt.ddt
@mark.django_db
class TestEnterpriseUtils(unittest.TestCase):
    """
    Tests for enterprise utility functions.
    """
    def setUp(self):
        """
        Set up test environment.
        """
        super(TestEnterpriseUtils, self).setUp()
        faker = FakerFactory.create()
        self.provider_id = faker.slug()  # pylint: disable=no-member
        self.uuid = faker.uuid4()  # pylint: disable=no-member
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=self.customer)

    @ddt.unpack
    @ddt.data(
        (
            EnterpriseCustomer,
            [
                "enterprise_customer_users",
                "pendingenterprisecustomeruser",
                "branding_configuration",
                "enterprise_customer_identity_providers",
                "enterprise_customer_catalogs",
                "enterprise_enrollment_template",
                "reporting_configurations",
                "pendingenterprisecustomeradminuser",
                "enterprise_customer_consent",
                "data_sharing_consent_page",
                "contentmetadataitemtransmission",
                "cornerstoneenterprisecustomerconfiguration",
                "degreedenterprisecustomerconfiguration",
                "canvasenterprisecustomerconfiguration",
                "blackboardenterprisecustomerconfiguration",
                "sapsuccessfactorsenterprisecustomerconfiguration",
                "moodleenterprisecustomerconfiguration",
                "xapilrsconfiguration",
                "created",
                "modified",
                "uuid",
                "name",
                "slug",
                "active",
                "country",
                "hide_course_original_price",
                "site",
                "enable_data_sharing_consent",
                "enforce_data_sharing_consent",
                "enable_audit_enrollment",
                "enable_audit_data_reporting",
                "replace_sensitive_sso_username",
                "enable_autocohorting",
                "customer_type",
                "enable_portal_code_management_screen",
                "enable_portal_reporting_config_screen",
                "enable_portal_subscription_management_screen",
                "enable_portal_saml_configuration_screen",
                "enable_learner_portal",
                "enable_integrated_customer_learner_portal_search",
                "enable_analytics_screen",
                "enable_slug_login",
                "contact_email",
                "default_contract_discount",
                "default_language",
            ]
        ),
        (
            EnterpriseCustomerUser,
            [
                "enterprise_enrollments",
                "enterpriseanalyticsuser",
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "user_id",
                "active",
                "linked",
            ]
        ),
        (
            EnterpriseCustomerBrandingConfiguration,
            [
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "logo",
                "primary_color",
                "secondary_color",
                "tertiary_color",
            ]
        ),
        (
            EnterpriseCustomerIdentityProvider,
            [
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "provider_id"
            ]
        ),
    )
    def test_get_all_field_names(self, model, expected_fields):
        actual_field_names = utils.get_all_field_names(model, excluded=['catalog'])
        assert sorted(actual_field_names) == sorted(expected_fields)

    @ddt.data(
        ("", ""),
        (
            "localhost:18387/api/v1/",
            "localhost:18387/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "http://localhost:18387/api/v1/",
            "http://localhost:18387/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "https://prod-site-discovery.example.com/api/v1/",
            "https://prod-site-discovery.example.com/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "https://discovery-site.subdomain.example.com/api/v1/",
            "https://discovery-site.subdomain.example.com/admin/catalogs/catalog/{catalog_id}/change/",
        ),
    )
    @ddt.unpack
    def test_catalog_admin_url_template(self, catalog_api_url, expected_url):
        """
        Validate that `get_catalog_admin_url_template` utility functions
        returns catalog admin page url template.

        Arguments:
            catalog_api_url (str): course catalog api url coming from DDT data decorator.
            expected_url (str): django admin catalog details page url coming from DDT data decorator.
        """
        with override_settings(COURSE_CATALOG_API_URL=catalog_api_url):
            url = utils.get_catalog_admin_url_template()
            assert url == expected_url

    @ddt.data(
        (7, "", ""),
        (
            7,
            "localhost:18387/api/v1/",
            "localhost:18387/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "http://localhost:18387/api/v1/",
            "http://localhost:18387/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "https://prod-site-discovery.example.com/api/v1/",
            "https://prod-site-discovery.example.com/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "https://discovery-site.subdomain.example.com/api/v1/",
            "https://discovery-site.subdomain.example.com/admin/catalogs/catalog/7/change/",
        ),
    )
    @ddt.unpack
    def test_catalog_admin_url(self, catalog_id, catalog_api_url, expected_url):
        """
        Validate that `get_catalog_admin_url` utility functions returns catalog admin page url.

        Arguments:
            catalog_id (int): catalog id coming from DDT data decorator.
            catalog_api_url (str): course catalog api url coming from DDT data decorator.
            expected_url (str): django admin catalog details page url coming from DDT data decorator.
        """
        with override_settings(COURSE_CATALOG_API_URL=catalog_api_url):
            url = utils.get_catalog_admin_url(catalog_id)
            assert url == expected_url

    @ddt.data(
        (EnterpriseCustomerFactory, [{'uuid': TEST_UUID}], True),
        (None, [{}], False)
    )
    @ddt.unpack
    def test_get_enterprise_customer(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        enterprise_customer = utils.get_enterprise_customer(TEST_UUID)
        if returns_obj:
            self.assertIsNotNone(enterprise_customer)
        else:
            self.assertIsNone(enterprise_customer)

    def test_get_enterprise_customer_user(self):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()

        assert utils.get_enterprise_customer_user(user.id, enterprise_customer.uuid) is None

        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        assert utils.get_enterprise_customer_user(user.id, enterprise_customer.uuid) == enterprise_customer_user

    @ddt.data(
        (
            {'class': PendingEnterpriseCustomerUserFactory, 'user_email': 'john@smith.com'},
            {
                'name': 'Demo Course',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-01-01'
            },
            'EdX',
            {
                'subject': 'You\'ve been enrolled in Demo Course!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'Hi!\n\nYou have been enrolled in Demo Course, a course offered by EdX. '
                    'This course begins Jan. 1, 2017. For more information, see the following'
                    ' link:\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Demo Course team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Hi!</p>\n<p>\nYou have been enrolled in <a href="http://lms.example.'
                            'com/courses">Demo Course</a>, a course offered by EdX. This course begins Jan. 1, '
                            '2017. For more information, see <a href="http://lms.example.com/courses">Demo Course'
                            '</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\nThe Demo Course team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'first_name': 'John', 'username': '', 'email': 'john@smith.com'},
            {
                'name': 'Enterprise Learning',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-06-23'
            },
            'Widgets, Inc',
            {
                'subject': 'You\'ve been enrolled in Enterprise Learning!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    u'Dear John,\n\nYou have been enrolled in Enterprise Learning, a course offered by Widgets, Inc. '
                    'This course begins June 23, 2017. For more information, see the following link:'
                    '\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Enterprise Learning team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear John,</p>\n<p>\nYou have been enrolled in <a href="http://'
                            'lms.example.com/courses">Enterprise Learning</a>, a course offered by Widgets, Inc. '
                            'This course begins June 23, 2017. For more information, see <a href="http://lms.example.'
                            'com/courses">Enterprise Learning</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\n'
                            'The Enterprise Learning team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'username': 'johnny_boy', 'email': 'john@smith.com', 'first_name': ''},
            {
                "name": "Master of Awesomeness",
                "url": "http://lms.example.com/courses",
                "type": "program",
                "branding": "MicroMaster",
                "start": "2017-04-15",
            },
            'MIT',
            {
                'subject': 'You\'ve been enrolled in Master of Awesomeness!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'Dear johnny_boy,\n\nYou have been enrolled in Master of Awesomeness, a MicroMaster program '
                    'offered by MIT. This program begins April 15, 2017. For more information, see the '
                    'following link:\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Master of Awesomeness team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear johnny_boy,</p>\n<p>\nYou have been enrolled in '
                            '<a href="http://lms.example.com/courses">Master of Awesomeness</a>, a MicroMaster '
                            'program offered by MIT. This program begins April 15, 2017. For more information, '
                            'see <a href="http://lms.example.com/courses">Master of Awesomeness</a>.\n</p>\n<p>\n'
                            'Thanks,\n</p>\n<p>\nThe Master of Awesomeness team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            None,
            {
                'name': 'coursename',
                'url': 'lms.example.com/courses',
                'type': 'program',
                'branding': 'MicroMaster',
                'start': '2017-01-01',
            },
            'EdX',
            {},
        ),
    )
    @ddt.unpack
    def test_send_email_notification_message(
            self,
            user,
            enrolled_in,
            enterprise_customer_name,
            expected_fields,
    ):
        """
        Test that we can successfully render and send an email message.
        """
        enrolled_in['start'] = datetime.datetime.strptime(enrolled_in['start'], '%Y-%m-%d')
        enterprise_customer = mock.MagicMock(spec=[], site=None)
        enterprise_customer.name = enterprise_customer_name
        if user is None:
            with raises(TypeError):
                utils.send_email_notification_message(
                    user,
                    enrolled_in,
                    enterprise_customer
                )
        else:
            conn = mail.get_connection()
            user_cls = user.pop('class')
            user = user_cls(**user)
            utils.send_email_notification_message(
                user,
                enrolled_in,
                enterprise_customer,
                email_connection=conn,
            )
            assert len(mail.outbox) == 1
            for field, val in expected_fields.items():
                assert getattr(mail.outbox[0], field) == val
            assert mail.outbox[0].connection is conn

    @ddt.data(
        (
            {'class': PendingEnterpriseCustomerUserFactory, 'user_email': 'john@smith.com'},
            {
                'name': 'Demo Course',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-01-01'
            },
            'EdX',
            {
                'subject': 'New course! Demo Course!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'plaintext_value'
                ),
                'alternatives': [
                    (
                        (
                            '<b>HTML value</b>'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'first_name': 'John', 'username': '', 'email': 'john@smith.com'},
            {
                'name': 'Enterprise Learning',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-06-23'
            },
            'Widgets, Inc',
            {
                'subject': 'New course! Enterprise Learning!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'plaintext_value'
                ),
                'alternatives': [
                    (
                        (
                            '<b>HTML value</b>'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'username': 'johnny_boy', 'email': 'john@smith.com', 'first_name': ''},
            {
                "name": "Master of Awesomeness",
                "url": "http://lms.example.com/courses",
                "type": "program",
                "branding": "MicroMaster",
                "start": "2017-04-15",
            },
            'MIT',
            {
                'subject': 'New course! Master of Awesomeness!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'plaintext_value'
                ),
                'alternatives': [
                    (
                        (
                            '<b>HTML value</b>'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            None,
            {
                'name': 'coursename',
                'url': 'lms.example.com/courses',
                'type': 'program',
                'branding': 'MicroMaster',
                'start': '2017-01-01',
            },
            'EdX',
            {}
        ),
    )
    @ddt.unpack
    def test_send_email_notification_message_with_site_defined_values(
            self,
            user,
            enrolled_in,
            enterprise_customer_name,
            expected_fields,
    ):
        """
        Test that we can successfully render and send an email message.
        """
        enrolled_in['start'] = datetime.datetime.strptime(enrolled_in['start'], '%Y-%m-%d')
        enterprise_customer = mock.MagicMock(
            enterprise_enrollment_template=mock.MagicMock(
                render_all_templates=mock.MagicMock(
                    return_value=(('plaintext_value', '<b>HTML value</b>', ))
                ),
                subject_line='New course! {course_name}!'
            ),
            site=None
        )
        enterprise_customer.name = enterprise_customer_name
        if user is None:
            with raises(TypeError):
                utils.send_email_notification_message(
                    user,
                    enrolled_in,
                    enterprise_customer
                )
        else:
            conn = mail.get_connection()
            user_cls = user.pop('class')
            user = user_cls(**user)
            utils.send_email_notification_message(
                user,
                enrolled_in,
                enterprise_customer,
                email_connection=conn,
            )
            assert len(mail.outbox) == 1
            for field, val in expected_fields.items():
                assert getattr(mail.outbox[0], field) == val
            assert mail.outbox[0].connection is conn

    @ddt.data(
        (
            {'class': PendingEnterpriseCustomerUserFactory, 'user_email': 'john@smith.com'},
            {
                'name': 'Demo Course',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-01-01'
            },
            'EdX',
            'Course! {course_name}',
            {
                'subject': 'Course! Demo Course',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'Hi!\n\nYou have been enrolled in Demo Course, a course offered by EdX. '
                    'This course begins Jan. 1, 2017. For more information, see the following'
                    ' link:\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Demo Course team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Hi!</p>\n<p>\nYou have been enrolled in <a href="http://lms.example.'
                            'com/courses">Demo Course</a>, a course offered by EdX. This course begins Jan. 1, '
                            '2017. For more information, see <a href="http://lms.example.com/courses">Demo Course'
                            '</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\nThe Demo Course team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'first_name': 'John', 'username': '', 'email': 'john@smith.com'},
            {
                'name': 'Enterprise Learning',
                'url': 'http://lms.example.com/courses',
                'type': 'course',
                'start': '2017-06-23'
            },
            'Widgets, Inc',
            '{bad_format_val} is a course!',  # Test that a string we can't format results in fallback to defaults
            {
                'subject': 'You\'ve been enrolled in Enterprise Learning!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    u'Dear John,\n\nYou have been enrolled in Enterprise Learning, a course offered by Widgets, Inc. '
                    'This course begins June 23, 2017. For more information, see the following link:'
                    '\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Enterprise Learning team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear John,</p>\n<p>\nYou have been enrolled in <a href="http://'
                            'lms.example.com/courses">Enterprise Learning</a>, a course offered by Widgets, Inc. '
                            'This course begins June 23, 2017. For more information, see <a href="http://lms.example.'
                            'com/courses">Enterprise Learning</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\nThe Enterprise'
                            ' Learning team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            {'class': UserFactory, 'username': 'johnny_boy', 'email': 'john@smith.com', 'first_name': ''},
            {
                "name": "Master of Awesomeness",
                "url": "http://lms.example.com/courses",
                "type": "program",
                "start": "2017-04-15",
            },
            'MIT',
            '',  # Test that an empty format string results in fallback to defaults
            {
                'subject': 'You\'ve been enrolled in Master of Awesomeness!',
                'from_email': 'course_staff@example.com',
                'to': [
                    'john@smith.com'
                ],
                'body': (
                    'Dear johnny_boy,\n\nYou have been enrolled in Master of Awesomeness, a  program '
                    'offered by MIT. This program begins April 15, 2017. For more information, see the '
                    'following link:\n\nhttp://lms.example.com/courses\n\nThanks,\n\nThe Master of Awesomeness team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear johnny_boy,</p>\n<p>\nYou have been '
                            'enrolled in <a href="http://lms.example.com/'
                            'courses">Master of Awesomeness</a>, a  program offered by MIT. This program '
                            'begins April 15, 2017. For more information, see <a href="http://lms.example.com/courses">'
                            'Master of Awesomeness</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\nThe Master of Awesomeness'
                            ' team\n</p>\n</body>\n</html>\n'
                        ),
                        'text/html'
                    )
                ],
                'attachments': [],
            }
        ),
        (
            None,
            {
                'name': 'coursename',
                'url': 'lms.example.com/courses',
                'type': 'program',
                'branding': 'MicroMaster',
                'start': '2017-01-01',
            },
            'EdX',
            '',
            {},
        ),
    )
    @ddt.unpack
    @override_settings(ENTERPRISE_ENROLLMENT_EMAIL_DEFAULT_SUBJECT_LINE='{bad_format} string')
    def test_send_email_notification_message_with_site_partially_defined_values(
            self,
            user,
            enrolled_in,
            enterprise_customer_name,
            subject_line,
            expected_fields,
    ):
        """
        Test ensures that, if only one of the templates has a defined value, we use
        the stock templates to avoid any confusion. Additionally, has some modifications
        to the stock values used elsewhere to make sure we hit other branches related
        to template string selection.
        """
        enrolled_in['start'] = datetime.datetime.strptime(enrolled_in['start'], '%Y-%m-%d')
        enterprise_customer = mock.MagicMock(
            enterprise_enrollment_template=mock.MagicMock(
                plaintext_template='',
                html_template='<b>hi there</b>',
                render_all_templates=mock.MagicMock(
                    return_value=(('plaintext_value', '<b>HTML value</b>', ))
                ),
                subject_line=subject_line
            ),
            site=None
        )
        enterprise_customer.name = enterprise_customer_name
        if user is None:
            with raises(TypeError):
                utils.send_email_notification_message(
                    user,
                    enrolled_in,
                    enterprise_customer
                )
        else:
            conn = mail.get_connection()
            user_cls = user.pop('class')
            user = user_cls(**user)
            utils.send_email_notification_message(
                user,
                enrolled_in,
                enterprise_customer,
                email_connection=conn,
            )
            assert len(mail.outbox) == 1
            for field, val in expected_fields.items():
                assert getattr(mail.outbox[0], field) == val
            assert mail.outbox[0].connection is conn

    @ddt.data(
        (
            'override@example.com',
            'override@example.com'
        ),
        (
            None,
            'course_staff@example.com'
        )
    )
    @ddt.unpack
    def test_send_email_notification_message_with_site_from_email_override(
            self,
            site_config_from_email_address,
            expected_from_email_address
    ):
        """
        Test that we can successfully override a from email address per site.
        """
        user = UserFactory(username='sal', email='sal@smith.com', first_name='sal')
        enrolled_in = {
            'name': 'Demo Course',
            'url': 'http://lms.example.com/courses',
            'type': 'course',
            'start': '2017-01-01'
        }
        enrolled_in['start'] = datetime.datetime.strptime(enrolled_in['start'], '%Y-%m-%d')

        site = SiteFactory()
        if site_config_from_email_address:
            site.configuration = mock.MagicMock(
                get_value=mock.MagicMock(
                    return_value=site_config_from_email_address
                )
            )

        enterprise_customer = mock.MagicMock(
            name='Example Corporation',
            enterprise_enrollment_template=mock.MagicMock(
                render_all_templates=mock.MagicMock(
                    return_value=(('plaintext_value', '<b>HTML value</b>', ))
                ),
                subject_line='New course! {course_name}!'
            ),
            site=site
        )

        conn = mail.get_connection()
        utils.send_email_notification_message(
            user,
            enrolled_in,
            enterprise_customer,
            email_connection=conn,
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].from_email == expected_from_email_address
        assert mail.outbox[0].connection is conn

    def test_get_enterprise_customer_for_user(self):
        """
        Test `get_enterprise_customer_for_user` helper method.
        """
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member

        user = UserFactory(id=1)
        ecu = EnterpriseCustomerUserFactory(
            user_id=user.id,
        )
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=ecu.enterprise_customer,
            provider_id=provider_id,
        )

        # Assert that correct enterprise customer is returned
        self.assertEqual(
            utils.get_enterprise_customer_for_user(auth_user=user),
            ecu.enterprise_customer,
        )

        # Assert that None is returned if user is not associated with any enterprise customer
        self.assertEqual(
            utils.get_enterprise_customer_for_user(auth_user=UserFactory(id=2)),
            None,
        )

    @ddt.data(
        (
            'lms.example.com/courses/course-v1:edx+test-course+T22017/',
            {},
            ['lms.example.com/courses/course-v1:edx+test-course+T22017/'],
        ),
        (
            'http://localhost/courses/course-v1:edx+test-course+T22017/',
            {},
            ['http://localhost/courses/course-v1:edx+test-course+T22017/'],
        ),
        (
            'http://open.edx/courses/course-v1:edx+test-course+T22017/?course=test-course',
            {},
            [
                'http://open.edx/courses/course-v1:edx+test-course+T22017/?',
                'course=test-course',
            ],
        ),
        (
            'http://open.edx/courses/course-v1:edx+test-course+T22017/',
            {
                'tpa_hint': 'test-shib',
                'referrer': 'edX',
            },
            [
                'http://open.edx/courses/course-v1:edx+test-course+T22017/?',
                'tpa_hint=test-shib',
                'referrer=edX',
            ],
        ),
        (
            'http://open.edx/courses/course-v1:edx+test-course+T22017/?course=test-course',
            {
                'tpa_hint': 'test-shib',
                'referrer': 'edX',
            },
            [
                'http://open.edx/courses/course-v1:edx+test-course+T22017/?',
                'tpa_hint=test-shib',
                'referrer=edX',
                'course=test-course',
            ],
        ),
    )
    @ddt.unpack
    def test_update_query_parameters(self, url, query_parameters, expected_url_parts):
        """
        Test `update_query_parameters` helper method.
        """
        url = utils.update_query_parameters(url, query_parameters)

        # Make sure all query parameters are present We can not assert whole urls because we can
        # not determine the position of these query parameters.
        # e.g. `http://<base>?course=test-course&tpa_hint=test-shib` and
        # `http://<base>?tpa_hint=test-shib&course=test-course` are both same urls but different strings.
        for url_part in expected_url_parts:
            assert url_part in url

    @ddt.data(
        (
            {
                'key': 'course-v1:edx+test-course+T22017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
            },
            {},
            ['http://testserver/course_modes/choose/course-v1:edx+test-course+T22017/'],
        ),
        (
            {
                'key': 'course-v1:edx+test-course+T22017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
            },
            {
                'tpa_hint': 'test-shib',
                'referrer': 'edX',
            },
            [
                'http://testserver/course_modes/choose/course-v1:edx+test-course+T22017/?',
                'tpa_hint=test-shib',
                'referrer=edX',
            ],
        ),
    )
    @ddt.unpack
    @override_settings(LMS_ROOT_URL='http://testserver/')
    def test_get_course_track_selection_url(self, course_run, query_parameters, expected_url_parts):
        """
        Test `get_course_track_selection_url` helper method.
        """
        course_root = "course_modes/choose/{course_id}/".format(course_id=course_run.get('key', ''))

        with mock.patch('enterprise.utils.reverse', return_value=course_root):
            url = utils.get_course_track_selection_url(course_run, query_parameters)

            # Make sure course run url returned by get_course_track_selection_url
            # contains all the expected url parts.
            # We can not assert whole urls because we can not determine the position of these query parameters.
            # e.g. `http://<base>?course=test-course&tpa_hint=test-shib` and
            # `http://<base>?tpa_hint=test-shib&course=test-course` are both same urls but different strings.
            for url_part in expected_url_parts:
                assert url_part in url

    def test_get_course_track_selection_url_raises_exception(self):
        """
        Test `get_course_track_selection_url` raises exception for missing `key` in course run.
        """
        with raises(KeyError):
            utils.get_course_track_selection_url({}, {})

    @ddt.data(
        ('{} hour', '{} hours', '{}-{} hours', 2, 4, '2-4 hours'),
        ('{} hour', '{} hours', '{}-{} hours', 2, 2, '2 hours'),
        ('{} hour', '{} hours', '{}-{} hours', 1, 1, '1 hour'),
        ('{} hour', '{} hours', '{}-{} hours', None, 1, '1 hour'),
        ('{} hour', '{} hours', '{}-{} hours', 1, None, '1 hour'),
        ('{} hour', '{} hours', '{}-{} hours', None, 3, '3 hours'),
        ('{} hour', '{} hours', '{}-{} hours', 3, None, '3 hours'),
        ('{} hour', '{} hours', '{}-{} hours', None, None, None),
    )
    @ddt.unpack
    def test_ungettext_min_max(self, singular, plural, range_text, min_val, max_val, expected_output):
        """
        ``ungettext_min_max`` returns the appropriate strings depending on a certain min & max.
        """
        assert utils.ungettext_min_max(singular, plural, range_text, min_val, max_val) == expected_output

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_get_configuration_value_with_openedx(self, config_mock):
        """
        ``get_configuration_value`` returns the appropriate non-default value when connected to Open edX.
        """
        config_mock.get_value.return_value = 'value'
        assert utils.get_configuration_value('value', default='default') == 'value'

    @mock.patch('enterprise.utils.get_url')
    def test_get_configuration_value_url_type(self, get_url_mock):
        """
        ``get_configuration_value`` returns the appropriate non-default value for URL types when in Open edX.
        """
        get_url_mock.return_value = 'value'
        assert utils.get_configuration_value('value', default='default', type='url') == 'value'

    def test_get_configuration_value_without_openedx(self):
        """
        ``get_configuration_value`` returns a default value of 'default' when not connected to Open edX.
        """
        assert utils.get_configuration_value('value', default='default') == 'default'

    def test_get_configuration_value_for_site_with_configuration(self):
        """
        ``get_configuration_value_for_site`` returns the key's value or the default in the site configuration.

        We do not test whether we get back the key's value or the default in particular, but just that
        the function returns a value through the configuration, rather than the default.
        """
        site = SiteFactory()
        site.configuration = mock.MagicMock(get_value=mock.MagicMock(return_value='value'))
        assert utils.get_configuration_value_for_site(site, 'key', 'default') == 'value'

    def test_get_configuration_value_for_site_without_configuration(self):
        """
        ``get_configuration_value_for_site`` returns the default because of no site configuration.
        """
        assert utils.get_configuration_value_for_site(SiteFactory(), 'key', 'default') == 'default'

    @ddt.data('GET', 'DELETE')
    def test_get_request_value_query_params(self, method):
        """
        Request value is retrieved from the query parameters and not posted data for certain methods.
        """
        request = mock.MagicMock(method=method, query_params={'key': 'query_params'}, data={'key': 'data'})
        assert utils.get_request_value(request, 'key') == 'query_params'

    def test_get_request_value_data(self):
        """
        Request value is retrieved from the posted data and not from the query parameters for certain methods.
        """
        request = mock.MagicMock(method='POST', query_params={'key': 'query_params'}, data={'key': 'data'})
        assert utils.get_request_value(request, 'key') == 'data'

    @ddt.data(
        (
            'MicroMasters Certificate',
            'A series of Master’s-level courses to advance your career, '
            'created by top universities and recognized by companies. '
            'MicroMasters Programs are credit-eligible, provide in-demand '
            'knowledge and may be applied to accelerate a Master’s Degree.',
        ),
        (
            'Professional Certificate',
            'Designed by industry leaders and top universities to enhance '
            'professional skills, Professional Certificates develop the '
            'proficiency and expertise that employers are looking for with '
            'specialized training and professional education.',
        ),
        (
            'XSeries Certificate',
            'Created by world-renowned experts and top universities, XSeries '
            'are designed to provide a deep understanding of key subjects '
            'through a series of courses. Complete the series to earn a valuable '
            'XSeries Certificate that illustrates your achievement.',
        ),
        (
            'Random Certificate',
            '',
        )
    )
    @ddt.unpack
    def test_get_program_type_description(self, program_type, expected_description):
        """
        ``get_program_type_description`` should return the appropriate description for any program type.
        """
        assert utils.get_program_type_description(program_type) == expected_description

    @mock.patch('enterprise.utils.segment')
    def test_track_event(self, analytics_mock):
        """
        ```track_event`` fires a track event to segment.
        """
        utils.track_event('user_id', 'event_name', 'properties')
        analytics_mock.track.assert_called_once()

    @mock.patch('enterprise.utils.track_event')
    def test_track_enrollment(self, track_event_mock):
        """
        ``track_enrollment`` invokes ``track_event`` with custom properties.
        """
        pathway = 'some-pathway'
        user_id = 123123
        course_run_id = 'course-v1:Some+edX+Course'
        url_path = '/some/url/path'
        utils.track_enrollment(pathway, user_id, course_run_id, url_path)
        track_event_mock.assert_called_once_with(user_id, 'edx.bi.user.enterprise.onboarding', {
            'pathway': pathway,
            'url_path': url_path,
            'course_run_id': course_run_id,
        })

    @ddt.data(
        ("2014-10-13T13:11:03Z", utils.parse_datetime("2014-10-13T13:11:03Z")),
        (datetime.datetime(2020, 5, 17), datetime.datetime(2020, 5, 17).replace(tzinfo=pytz.UTC)),
        (None, None)
    )
    @ddt.unpack
    def test_parse_datetime_handle_invalid(self, datetime_value, expected_parsed_datetime):
        """
        ``parse_datetime_handle_invalid`` wraps ``parse_datetime`` such that it returns ``None`` for any bad types.
        """
        assert utils.parse_datetime_handle_invalid(datetime_value) == expected_parsed_datetime

    @ddt.data(
        (
            {
                "min_effort": 2,
                "max_effort": 3,
                "weeks_to_complete": 3,
            },
            '2-3 hours a week for 3 weeks. ',
        ),
        (
            {
                "min_effort": 0,
                "max_effort": 3,
                "weeks_to_complete": 3,
            },
            '',
        ),
        (
            {
                "min_effort": 2,
                "max_effort": '',
                "weeks_to_complete": 3,
            },
            '',
        ),
        (
            {
                "min_effort": 2,
                "max_effort": 2,
                "weeks_to_complete": None,
            },
            '',
        ),
        (
            {
                "min_effort": '',
                "max_effort": 0,
                "weeks_to_complete": None,
            },
            '',
        ),

    )
    @ddt.unpack
    def test_get_course_run_duration_info(self, course_run, expected_duration_info):
        """
        ``get_course_run_duration_info`` returns the course run duration info
        """
        assert utils.get_course_run_duration_info(course_run) == expected_duration_info

    @ddt.data(
        (
            {
                "status": "published",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": "2999-10-13T13:11:04Z",
            },
            True,
        ),
        (
            {
                "status": "published",
                "end": None,
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": "2999-10-13T13:11:04Z"
            },
            True,
        ),
        (
            {
                "status": "published",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": None,
                "enrollment_end": "2999-10-13T13:11:04Z"
            },
            True,
        ),
        (
            {
                "status": "published",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": None
            },
            True,
        ),
        (
            {
                "status": "published",
                "end": "2014-10-13T13:11:01Z",  # end < now
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": "2999-10-13T13:11:04Z",
            },
            False,
        ),
        (
            {
                "status": "published",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": "2999-10-13T13:11:03Z",  # enrollment_start > now
                "enrollment_end": "3000-10-13T13:11:04Z",
            },
            False,
        ),
        (
            {
                "status": "published",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": "2014-10-13T13:11:04Z",  # enrollment_end < now
            },
            False,
        ),
        (
            {
                "status": "unpublished",
                "end": "3000-10-13T13:11:01Z",
                "enrollment_start": "2014-10-13T13:11:03Z",
                "enrollment_end": "3000-10-13T13:11:04Z",  # enrollment_end < now
            },
            False,
        ),
    )
    @ddt.unpack
    def test_is_course_run_enrollable(self, course_run, expected_enrollment_eligibility):
        """
        ``is_course_run_enrollable`` returns whether the course run is enrollable.

        We check that the function returns:
        - False on end < now.
        - False on enrollment_end < now.
        - False on enrollment_start > now.
        - False on is_course_run_published = False
        - True if none of the above plus, optionally, if any of the values are NULL.
        """
        assert utils.is_course_run_enrollable(course_run) == expected_enrollment_eligibility

    @ddt.data(
        (
            [],
            False,
        ),
        (
            [
                {
                    "status": "published",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2999-10-13T13:11:03Z",  # enrollment_start > now
                    "enrollment_end": "3000-10-13T13:11:04Z",
                },
                {
                    "status": "published",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                },
            ],
            True,
        ),
        (
            [
                {
                    "status": "published",
                    "availability": "Archived",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                },
                {
                    "status": "published",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                },
            ],
            True,
        ),
        (
            [
                {
                    "status": "published",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                }
            ],
            True,
        ),
        (
            [
                {
                    "status": "published",
                    "availability": "Archived",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                }
            ],
            False,
        ),
        (
            [
                {
                    "status": "published",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                }
            ],
            True,
        ),
        (
            [
                {
                    "status": "unpublished",
                    "availability": "Current",
                    "end": "3000-10-13T13:11:01Z",
                    "enrollment_start": "2014-10-13T13:11:03Z",
                    "enrollment_end": "2999-10-13T13:11:04Z",
                }
            ],
            False,
        ),
    )
    @ddt.unpack
    def test_contains_course_run_available_for_enrollment(self, course_runs, expected_enrollment_eligibility):
        """
        tests contains_course_run_available_for_enrollment functionality
        """
        assert utils.has_course_run_available_for_enrollment(course_runs) == expected_enrollment_eligibility

    @ddt.data(
        ({"seats": [{"type": "verified", "upgrade_deadline": "3000-10-13T13:11:04Z"}]}, True),
        ({"seats": [{"type": "verified", "upgrade_deadline": None}]}, True),
        ({"seats": [{"type": "verified"}]}, True),
        ({"seats": [{"type": "verified", "upgrade_deadline": "1977-10-13T13:11:04Z"}]}, False),
        ({"seats": [{"type": "audit"}]}, False),
        ({}, False),
    )
    @ddt.unpack
    def test_is_course_run_upgradeable(self, course_run, expected_upgradeability):
        """
        ``is_course_run_upgradeable`` returns whether the course run is eligible
        for an upgrade to the verified track.
        """
        assert utils.is_course_run_upgradeable(course_run) == expected_upgradeability

    @ddt.data(
        ({"status": "published"}, True),
        ({"status": "unpublished"}, False)
    )
    @ddt.unpack
    def test_is_course_published(self, course_run, expected_response):
        """
        ``is_course_run_published`` returns whether the course run is considered "published"
        given its metadata structure and values.
        """
        assert utils.is_course_run_published(course_run) == expected_response

    @ddt.data(
        ({"start": "3000-10-13T13:11:04Z"}, utils.parse_datetime_handle_invalid("3000-10-13T13:11:04Z")),
        ({}, None),
    )
    @ddt.unpack
    def test_get_course_run_start(self, course_run, expected_start):
        """
        ``get_course_run_start`` returns the start date given the course run dict.
        """
        assert utils.get_course_run_start(course_run) == expected_start

    def test_get_course_run_start_with_default(self):
        """
        ``get_course_run_start`` returns the appropriate default start date.
        """
        now = datetime.datetime.now()
        assert utils.get_course_run_start({}) is None
        assert utils.get_course_run_start({}, now) == now

    @ddt.data(
        (
            fake_catalog_api.create_course_run_dict(
                end=DATETIME_NOW + datetime.timedelta(days=20),
                weeks_to_complete=5
            ),
            True,
        ),
        (
            fake_catalog_api.create_course_run_dict(
                end=DATETIME_NOW + datetime.timedelta(days=20),
                weeks_to_complete=2
            ),
            False,
        ),
        (
            fake_catalog_api.create_course_run_dict(
                end=DATETIME_NOW + datetime.timedelta(days=20),
                weeks_to_complete=None
            ),
            False,
        ),
    )
    @ddt.unpack
    def test_is_course_run_about_to_end(self, course_run, expected_boolean):
        """
        ``is_course_run_about_to_end`` returns the boolean is course_run about to end.
        """
        assert utils.is_course_run_about_to_end(course_run) == expected_boolean

    @ddt.data(
        (
            # Test with two enrollable/upgradeable course runs.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(),
                    fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z"),
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z"),
        ),
        (
            # Test with one enrollable course run.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(),
                    fake_catalog_api.create_course_run_dict(
                        enrollment_end="2014-10-14T13:11:03Z",
                    ),
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(),
        ),
        (
            # Test with no enrollable course runs.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(enrollment_end="2014-10-14T13:11:03Z"),
                    fake_catalog_api.create_course_run_dict(
                        start="2014-10-15T13:11:03Z",
                        enrollment_end="2014-10-14T13:11:03Z",
                    ),
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(
                start="2014-10-15T13:11:03Z",
                enrollment_end="2014-10-14T13:11:03Z",
            ),
        ),
        (
            # Test with one upgradeable course run.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(),
                    fake_catalog_api.create_course_run_dict(
                        upgrade_deadline="2014-10-14T13:11:03Z",
                    ),
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(),
        ),
        (
            # Test with no upgradeable course runs.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(upgrade_deadline="2014-10-14T13:11:03Z"),
                    fake_catalog_api.create_course_run_dict(
                        start="2014-10-15T13:11:03Z",
                        upgrade_deadline="2014-10-14T13:11:03Z",
                    ),
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(
                start="2014-10-15T13:11:03Z",
                upgrade_deadline="2014-10-14T13:11:03Z",
            ),
        ),
        (
            # Test with current availability.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(
                        end=DATETIME_NOW + datetime.timedelta(days=20),
                        availability='Current'
                    ),
                    fake_catalog_api.create_course_run_dict(end="2099-01-14T13:11:03Z")
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(
                end=DATETIME_NOW + datetime.timedelta(days=20),
                availability='Current'
            ),
        ),
        (
            # Test with current availability.
            {
                "course_runs": [
                    fake_catalog_api.create_course_run_dict(
                        end=DATETIME_NOW + datetime.timedelta(days=20),
                        weeks_to_complete=4,
                        availability='Current',
                    ),
                    fake_catalog_api.create_course_run_dict(end="2021-10-14T13:11:03Z")
                ],
            },
            [],
            fake_catalog_api.create_course_run_dict(end="2021-10-14T13:11:03Z"),
        ),
        (   # It will return the active run
            {
                "course_runs": [],
            },
            [fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z")],
            fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z"),
        ),
        (   # it will return the closest active run
            {
                "course_runs": [],
            },
            [
                fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z"),
                fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
            ],
            fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
        ),
        (
            # Test with no course runs.
            {
                "course_runs": [],
            },
            [],
            None
        ),
    )
    @ddt.unpack
    def test_get_current_course_run(self, course, users_active_course_runs, expected_course_run):
        """
        ``get_current_course_run`` returns the current course run for the given course dictionary.
        """
        assert utils.get_current_course_run(course, users_active_course_runs) == expected_course_run

    @ddt.data(
        (
            [
                fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
                fake_catalog_api.create_course_run_dict(start="2014-10-15T13:11:03Z"),
            ],
            fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
        ),
        (
            [
                fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
            ],
            fake_catalog_api.create_course_run_dict(start="2019-10-15T13:11:03Z"),
        ),

    )
    @ddt.unpack
    def test_get_closest_course_run(self, course_runs, expected_course_run):
        """
        ``get_closest_course_run`` returns the closest course run.
        """
        assert utils.get_closest_course_run(course_runs) == expected_course_run

    @ddt.data(
        (
            {
                "course_runs":
                    [
                        {'key': 'fake-key1'},
                        {'key': 'fake-key2'}
                    ],
            },
            [
                {
                    'is_active': True,
                    'course_details': {'course_id': 'fake-key1'}
                },
                {
                    'is_active': False,
                    'course_details': {'course_id': 'fake-key2'}
                }
            ],
            [
                {'key': 'fake-key1'},
            ],
        ),
        (
            {
                "course_runs":
                    [
                        {'key': 'fake-key1'},
                        {'key': 'fake-key2'}
                    ],
            },
            [
                {
                    'is_active': True,
                    'course_details': {'course_id': 'fake-key1'}
                },
                {
                    'is_active': True,
                    'course_details': {'course_id': 'fake-key2'}
                }
            ],
            [
                {'key': 'fake-key1'},
                {'key': 'fake-key2'}
            ],
        ),
        (
            {
                "course_runs":
                    [
                        {'key': 'fake-key1'},
                        {'key': 'fake-key2'}
                    ],
            },
            [
                {
                    'is_active': False,
                    'course_details': {'course_id': 'fake-key1'}
                },
                {
                    'is_active': False,
                    'course_details': {'course_id': 'fake-key2'}
                }
            ],
            [],
        ),
        (
            {
                "course_runs": [],
            },
            [
                {
                    'is_active': True,
                    'course_details': {'course_id': 'fake-key1'}
                }
            ],
            [],
        ),

    )
    @ddt.unpack
    def test_get_active_course_runs(self, course, users_all_enrolled_courses, expected_course_run):
        """
        ``get_active_course_runs`` returns active course runs of given course's course runs.
        """
        assert utils.get_active_course_runs(course, users_all_enrolled_courses) == expected_course_run


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorsUtils(unittest.TestCase):
    """
    Tests for sap success factors utility functions.
    """

    def setUp(self):
        """
        Set up test environment.
        """
        super(TestSAPSuccessFactorsUtils, self).setUp()
        faker = FakerFactory.create()
        self.user = UserFactory()
        self.uuid = faker.uuid4()  # pylint: disable=no-member
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        self.enterprise_configuration = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
        )

    @ddt.data(
        (
            {'mode': 'enroll', 'number': 0},
            {'mode': 'audit', 'number': 1},
            {'mode': 'another_audit', 'number': 2},
            {'mode': 'enroll', 'number': 3},
            {'mode': 'audit', 'number': 4},
        )
    )
    @override_settings(ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES=['audit', 'another_audit'])
    def test_filter_audit_course_modes(self, course_modes):
        # when the audit enrollment flag is disabled
        self.customer.enable_audit_enrollment = False
        # course modes are filtered out if their mode is in the ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES setting
        filtered_course_modes = utils.filter_audit_course_modes(self.customer, course_modes)
        assert len(filtered_course_modes) == 2
        result = [course_mode['number'] for course_mode in filtered_course_modes]
        expected = [0, 3]
        self.assertListEqual(result, expected)

        # when the audit enrollment flag is enabled
        self.customer.enable_audit_enrollment = True
        # audit course modes are not filtered out
        filtered_course_modes = utils.filter_audit_course_modes(self.customer, course_modes)
        assert len(filtered_course_modes) == 5


@mark.django_db
@ddt.ddt
class TestValidateEmailToLink(unittest.TestCase):
    """
    Tests for :method:`validate_email_to_link`.
    """

    def test_validate_email_to_link_normal(self):
        email = FAKER.email()  # pylint: disable=no-member
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 0, \
            "Precondition check - should not have PendingEnterpriseCustomerUser"
        assert EnterpriseCustomerUser.objects.count() == 0, \
            "Precondition check - should not have EnterpriseCustomerUser"

        exists = utils.validate_email_to_link(email)  # should not raise any Exceptions
        assert exists is False

    @ddt.unpack
    @ddt.data(
        ("something", "something", utils.ValidationMessages.INVALID_EMAIL),
        ("something_again@", "something_else", utils.ValidationMessages.INVALID_EMAIL)
    )
    def test_validate_email_to_link_invalid_email(self, email, raw_email, msg_template):
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) is None, \
            "Precondition check - should not have EnterpriseCustomerUser or PendingEnterpriseCustomerUser"

        expected_message = msg_template.format(argument=raw_email)

        with raises(ValidationError, match=expected_message):
            utils.validate_email_to_link(email, raw_email)

    @ddt.data(True, False)
    def test_validate_email_to_link_existing_user_record(self, ignore_existing):
        user = UserFactory()
        email = user.email
        existing_record = EnterpriseCustomerUserFactory(user_id=user.id)
        assert not PendingEnterpriseCustomerUser.objects.exists(), \
            "Precondition check - should not have PendingEnterpriseCustomerUser"
        assert EnterpriseCustomerUser.objects.get(user_id=user.id) == existing_record, \
            "Precondition check - should have EnterpriseCustomerUser"

        if ignore_existing:
            exists = utils.validate_email_to_link(email, ignore_existing=True)
            assert exists
        else:
            expected_message = utils.ValidationMessages.USER_ALREADY_REGISTERED.format(
                email=email, ec_name=existing_record.enterprise_customer.name
            )

            with raises(ValidationError, match=expected_message):
                utils.validate_email_to_link(email)

    @ddt.data(True, False)
    def test_validate_email_to_link_existing_pending_record(self, ignore_existing):
        email = FAKER.email()  # pylint: disable=no-member
        existing_record = PendingEnterpriseCustomerUserFactory(user_email=email)
        assert PendingEnterpriseCustomerUser.objects.get(user_email=email) == existing_record, \
            "Precondition check - should have PendingEnterpriseCustomerUser"
        assert not EnterpriseCustomerUser.objects.exists(), \
            "Precondition check - should not have EnterpriseCustomerUser"

        if ignore_existing:
            exists = utils.validate_email_to_link(email, ignore_existing=True)
            assert exists
        else:
            expected_message = utils.ValidationMessages.USER_ALREADY_REGISTERED.format(
                email=email, ec_name=existing_record.enterprise_customer.name
            )

            with raises(ValidationError, match=expected_message):
                exists = utils.validate_email_to_link(email)
