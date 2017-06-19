# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import unittest

import ddt
import mock
import six
from faker import Factory as FakerFactory
from integrated_channels.integrated_channel.course_metadata import BaseCourseExporter
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.utils import SapCourseExporter, get_launch_url
from pytest import mark, raises

from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.http import Http404
from django.test import RequestFactory, override_settings

from enterprise import utils
from enterprise.django_compatibility import reverse
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    UserDataSharingConsentAudit,
)
from enterprise.utils import (
    consent_necessary_for_course,
    disable_for_loaddata,
    filter_audit_course_modes,
    get_all_field_names,
    get_enterprise_customer_user,
    is_consent_required_for_user,
)
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    SiteFactory,
    UserDataSharingConsentAuditFactory,
    UserFactory,
)


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
        self.provider_id = faker.slug()
        self.uuid = faker.uuid4()
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=self.customer)

    @staticmethod
    def get_magic_name(value):
        """
        Return value suitable for __name__ attribute.

        For python2, __name__ must be str, while for python3 it must be unicode (as there are no str at all).

        Arguments:
            value basestring: string to "convert"

        Returns:
            str or unicode
        """
        return str(value) if six.PY2 else value

    @staticmethod
    def mock_view_function():
        """
        Return mock function for views that are decorated.
        """
        view_function = mock.Mock()
        view_function.__name__ = str('view_function') if six.PY2 else 'view_function'
        return view_function

    def test_get_idp_choices(self):
        """
        Test get_idp_choices returns correct options for choice field or returns None if
        thirdParty_auth is not installed.
        """
        options = utils.get_idp_choices()
        self.assertIsNone(options)
        expected_list = [('', '-'*7), ('test1', 'test1'), ('test2', 'test2')]

        with mock.patch('enterprise.utils.Registry') as mock_registry:
            mock_registry.enabled = mock_get_available_idps(['test1', 'test2'])

            choices = utils.get_idp_choices()
            self.assertListEqual(choices, expected_list)

    def test_get_identity_provider(self):
        """
        Test get_identity_provider returns correct value.
        """
        faker = FakerFactory.create()
        name = faker.name()
        provider_id = faker.slug()

        # test that get_identity_provider returns None if third_party_auth is not available.
        identity_provider = utils.get_identity_provider(provider_id=provider_id)
        assert identity_provider is None

        # test that get_identity_provider does not return None if third_party_auth is  available.
        with mock.patch('enterprise.utils.Registry') as mock_registry:
            mock_registry.get.return_value.configure_mock(name=name, provider_id=provider_id)
            identity_provider = utils.get_identity_provider(provider_id=provider_id)
            assert identity_provider is not None

    @ddt.unpack
    @ddt.data(
        (
            EnterpriseCustomer,
            [
                "enterprise_customer_users",
                "pendingenterprisecustomeruser",
                "branding_configuration",
                "enterprise_customer_identity_provider",
                "enterprise_customer_entitlements",
                "sapsuccessfactorsenterprisecustomerconfiguration",
                "created",
                "modified",
                "uuid",
                "name",
                "catalog",
                "active",
                "site",
                "enable_data_sharing_consent",
                "enforce_data_sharing_consent",
                "enable_audit_enrollment",
                "require_account_level_consent",
            ]
        ),
        (
            EnterpriseCustomerUser,
            [
                "data_sharing_consent",
                "enterprise_enrollments",
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "user_id",
            ]
        ),
        (
            EnterpriseCustomerBrandingConfiguration,
            [
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "logo"
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
        actual_field_names = get_all_field_names(model)
        assert actual_field_names == expected_fields

    @ddt.data(True, False)
    def test_disable_for_loaddata(self, raw):
        signal_handler_mock = mock.MagicMock()
        signal_handler_mock.__name__ = self.get_magic_name("Irrelevant")
        wrapped_handler = disable_for_loaddata(signal_handler_mock)

        wrapped_handler(raw=raw)

        assert signal_handler_mock.called != raw

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
        (True, True, EnterpriseCustomer.AT_ENROLLMENT, False),
        (None, True, EnterpriseCustomer.AT_ENROLLMENT, True),
        (True, False, EnterpriseCustomer.AT_ENROLLMENT, False),
        (False, False, EnterpriseCustomer.AT_ENROLLMENT, False),
        (None, True, EnterpriseCustomer.AT_LOGIN, True),
        (False, False, EnterpriseCustomer.AT_LOGIN, False),
    )
    @ddt.unpack
    def test_consent_necessary_for_course(
            self,
            consent_provided_state,
            ec_consent_enabled,
            ec_consent_enforcement,
            expected_result
    ):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=ec_consent_enabled,
            enforce_data_sharing_consent=ec_consent_enforcement,
        )
        enterprise_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=enterprise_user,
            consent_granted=consent_provided_state,
            course_id=course_id
        )
        assert consent_necessary_for_course(user, course_id) is expected_result
        account_consent = UserDataSharingConsentAuditFactory(
            user=enterprise_user,
            state=UserDataSharingConsentAudit.ENABLED,
        )
        assert consent_necessary_for_course(user, course_id) is False
        account_consent.delete()  # pylint: disable=no-member
        enrollment.delete()
        assert consent_necessary_for_course(user, course_id) is False

    def test_get_enterprise_customer_user(self):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()

        assert get_enterprise_customer_user(user.id, enterprise_customer.uuid) is None

        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        assert get_enterprise_customer_user(user.id, enterprise_customer.uuid) == enterprise_customer_user

    @ddt.data(
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED, False),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED, True),
        (False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED, False),
        (False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED, False),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED, False),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED, True),
        (False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED, False),
        (False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED, False),
    )
    @ddt.unpack
    def test_is_consent_required_for_user(
            self,
            ec_consent_enabled,
            ec_consent_enforcement,
            learner_consent_state,
            expected_result
    ):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=ec_consent_enabled,
            enforce_data_sharing_consent=ec_consent_enforcement,
        )
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        UserDataSharingConsentAuditFactory(
            user=enterprise_customer_user,
            state=learner_consent_state,
        )
        assert is_consent_required_for_user(enterprise_customer_user) is expected_result

    @ddt.data(
        (True, EnterpriseCustomer.AT_ENROLLMENT, True, False),
        (True, EnterpriseCustomer.AT_ENROLLMENT, False, True),
        (False, EnterpriseCustomer.AT_ENROLLMENT, True, False),
        (False, EnterpriseCustomer.AT_ENROLLMENT, False, False),
        (True, EnterpriseCustomer.AT_LOGIN, True, False),
        (True, EnterpriseCustomer.AT_LOGIN, False, True),
        (False, EnterpriseCustomer.AT_LOGIN, True, False),
        (False, EnterpriseCustomer.AT_LOGIN, False, False),
    )
    @ddt.unpack
    def test_is_consent_required_for_user_with_course(
            self,
            ec_consent_enabled,
            ec_consent_enforcement,
            learner_consent_state,
            expected_result
    ):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=ec_consent_enabled,
            enforce_data_sharing_consent=ec_consent_enforcement,
        )
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=enterprise_customer_user,
            consent_granted=learner_consent_state,
            course_id=course_id
        )
        assert is_consent_required_for_user(enterprise_customer_user, course_id) is expected_result

    @ddt.data(
        (
            {'class': PendingEnterpriseCustomerUserFactory, 'user_email': 'john@smith.com'},
            {
                'name': 'Demo Course',
                'url': 'http://localhost:8000/courses',
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
                    ' link:\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Demo Course team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Hi!</p>\n<p>\nYou have been enrolled in <a href="http://localhost'
                            ':8000/courses">Demo Course</a>, a course offered by EdX. This course begins Jan. 1, '
                            '2017. For more information, see <a href="http://localhost:8000/courses">Demo Course'
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
                'url': 'http://localhost:8000/courses',
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
                    '\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Enterprise Learning team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear John,</p>\n<p>\nYou have been enrolled in <a href="http://'
                            'localhost:8000/courses">Enterprise Learning</a>, a course offered by Widgets, Inc. '
                            'This course begins June 23, 2017. For more information, see <a href="http://localhost'
                            ':8000/courses">Enterprise Learning</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\n'
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
                "url": "http://localhost:8000/courses",
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
                    'following link:\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Master of Awesomeness team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear johnny_boy,</p>\n<p>\nYou have been enrolled in '
                            '<a href="http://localhost:8000/courses">Master of Awesomeness</a>, a MicroMaster '
                            'program offered by MIT. This program begins April 15, 2017. For more information, '
                            'see <a href="http://localhost:8000/courses">Master of Awesomeness</a>.\n</p>\n<p>\n'
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
                'url': 'localhost:8000/courses',
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
        enterprise_customer = mock.MagicMock(
            site=mock.MagicMock(spec=[])
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
                'url': 'http://localhost:8000/courses',
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
                'url': 'http://localhost:8000/courses',
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
                "url": "http://localhost:8000/courses",
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
                'url': 'localhost:8000/courses',
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
            site=mock.MagicMock(
                enterprise_enrollment_template=mock.MagicMock(
                    render_all_templates=mock.MagicMock(
                        return_value=(('plaintext_value', '<b>HTML value</b>', ))
                    ),
                    subject_line='New course! {course_name}!'
                )
            )
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
                'url': 'http://localhost:8000/courses',
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
                    ' link:\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Demo Course team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Hi!</p>\n<p>\nYou have been enrolled in <a href="http://localhost:'
                            '8000/courses">Demo Course</a>, a course offered by EdX. This course begins Jan. 1, '
                            '2017. For more information, see <a href="http://localhost:8000/courses">Demo Course'
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
                'url': 'http://localhost:8000/courses',
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
                    '\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Enterprise Learning team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear John,</p>\n<p>\nYou have been enrolled in <a href="http://'
                            'localhost:8000/courses">Enterprise Learning</a>, a course offered by Widgets, Inc. '
                            'This course begins June 23, 2017. For more information, see <a href="http://localhost'
                            ':8000/courses">Enterprise Learning</a>.\n</p>\n<p>\nThanks,\n</p>\n<p>\nThe Enterprise'
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
                "url": "http://localhost:8000/courses",
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
                    'following link:\n\nhttp://localhost:8000/courses\n\nThanks,\n\nThe Master of Awesomeness team\n'
                ),
                'alternatives': [
                    (
                        (
                            '<html>\n<body>\n<p>Dear johnny_boy,</p>\n<p>\nYou have been '
                            'enrolled in <a href="http://localhost:8000/'
                            'courses">Master of Awesomeness</a>, a  program offered by MIT. This program '
                            'begins April 15, 2017. For more information, see <a href="http://localhost:8000/courses">'
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
                'url': 'localhost:8000/courses',
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
            site=mock.MagicMock(
                enterprise_enrollment_template=mock.MagicMock(
                    plaintext_template='',
                    html_template='<b>hi there</b>',
                    render_all_templates=mock.MagicMock(
                        return_value=(('plaintext_value', '<b>HTML value</b>', ))
                    ),
                    subject_line=subject_line
                )
            )
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

    def test_get_enterprise_customer_for_user(self):
        """
        Test `get_enterprise_customer_for_user` helper method.
        """
        faker = FakerFactory.create()
        provider_id = faker.slug()

        user = UserFactory()
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
            utils.get_enterprise_customer_for_user(auth_user=UserFactory()),
            None,
        )

    @ddt.data(
        (
            'localhost:8000/courses/course-v1:edx+test-course+T22017/',
            {},
            ['localhost:8000/courses/course-v1:edx+test-course+T22017/'],
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

    @mock.patch('integrated_channels.integrated_channel.course_metadata.get_course_runs')
    def test_base_course_exporter_serialized_data_raises(self, mock_get_course_runs):
        mock_get_course_runs.return_value = []
        mock_user = mock.MagicMock()
        mock_plugin_configuration = mock.MagicMock()
        exporter = BaseCourseExporter(mock_user, mock_plugin_configuration)
        with raises(NotImplementedError):
            exporter.get_serialized_data()

    @ddt.data(
        {},  # Missing required parameter `enterprise_uuid` arguments in kwargs
        {'enterprise_uuid': ''},  # Required parameter `enterprise_uuid` with empty value in kwargs.
        {'enterprise_uuid': FakerFactory.create().uuid4()},  # Invalid value of `enterprise_uuid` in kwargs.
    )
    def test_enterprise_login_required_raises_404(self, kwargs):
        """
        Test that the decorator `enterprise_login_required` raises `Http404`
        error when called with invalid or missing arguments.
        """
        view_function = self.mock_view_function()
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, 'course-v1:edX+DemoX+Demo_Course'],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        with raises(Http404):
            utils.enterprise_login_required(view_function)(request, **kwargs)

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required_redirects_for_anonymous_users(self, mock_registry):
        """
        Test that the decorator `enterprise_login_required` returns Http
        Redirect for anonymous users.
        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=False)
        view_function = self.mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = AnonymousUser()

        response = utils.enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when an anonymous
        # user tries to access enterprise course enrollment page.
        assert response.status_code == 302

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required(self, mock_registry):
        """
        Test that the enterprise login decorator calls the view function.

        Test that the decorator `enterprise_login_required` calls the view
        function when:
            1. `enterprise_uuid` is provided and corresponding enterprise
                customer exists in database.
            2. User making the request is authenticated.

        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=False)
        view_function = self.mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        utils.enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @mock.patch('enterprise.utils.get_identity_provider', side_effect=ValueError)
    def test_enterprise_login_required_no_sso_provider(self, mock_registry):  # pylint: disable=unused-argument
        """
        Test that the enterprise login decorator calls the view function when no sso provider is configured.
        """

        view_function = self.mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        utils.enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required_with_drop_existing_session(self, mock_registry):
        """
        Test that the enterprise login decorator redirects authenticated users with the appropriate provider config.
        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=True)
        view_function = self.mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        response = utils.enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when a logged in user comes in
        # with an sso provider set to drop existing sessions
        assert response.status_code == 302


def get_transformed_course_metadata(course_id, status):
    """
    Return the expected transformed data for TestSAPSuccessFactorsUtils tests.
    """
    return {
        'courseID': course_id,
        'providerID': 'EDX',
        'status': status,
        'title': [{'locale': 'English', 'value': ''}],
        'description': [{'locale': 'English', 'value': ''}],
        'thumbnailURI': '',
        'content': [
            {
                'providerID': 'EDX',
                'launchURL': '',
                'contentTitle': '',
                'contentID': course_id,
                'launchType': 3,
                'mobileEnabled': 'false',
            }
        ],
        'price': [],
        'schedule': [
            {
                'startDate': 0,
                'endDate': 2147483647000,
                'active': True
            }
        ],
        'revisionNumber': 1,
    }


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
        self.uuid = faker.uuid4()
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        self.plugin_configuration = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
        )

    @mock.patch('integrated_channels.integrated_channel.course_metadata.get_course_runs')
    @mock.patch('integrated_channels.sap_success_factors.utils.get_course_track_selection_url')
    @ddt.data(
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
                {'key': 'course2', 'availability': 'Archived'},
            ],
            # previous audit summary
            {},
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE)
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
                {'key': 'course2', 'availability': 'Archived'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'INACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'INACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
                get_transformed_course_metadata('course2', SapCourseExporter.STATUS_INACTIVE),
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
                {'key': 'course2', 'availability': 'Archived'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'INACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
                get_transformed_course_metadata('course2', SapCourseExporter.STATUS_INACTIVE),
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'INACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': False, 'status': 'INACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
                {
                    'courseID': 'course2',
                    'providerID': 'EDX',
                    'status': SapCourseExporter.STATUS_INACTIVE,
                    'title': [{'locale': 'English', 'value': 'course2'}],
                    'content': [
                        {
                            'providerID': 'EDX',
                            'launchURL': '',
                            'contentTitle': 'Course Description',
                            'launchType': 3,
                            'contentID': 'course2',
                        }
                    ],
                },
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
                {'key': 'course2', 'availability': 'Current'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'INACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
                get_transformed_course_metadata('course2', SapCourseExporter.STATUS_ACTIVE),
            ],
        ),
        (
            # course runs
            [
                {'key': 'course1', 'availability': 'Current'},
                {'key': 'course2', 'availability': 'Current'},
            ],
            # previous audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected audit summary
            {
                'course1': {'in_catalog': True, 'status': 'ACTIVE'},
                'course2': {'in_catalog': True, 'status': 'ACTIVE'},
            },
            # expected courses
            [
                get_transformed_course_metadata('course1', SapCourseExporter.STATUS_ACTIVE),
                get_transformed_course_metadata('course2', SapCourseExporter.STATUS_ACTIVE),
            ],
        ),
    )
    @ddt.unpack
    def test_resolve_removed_courses(
            self,
            course_runs,
            previous_audit_summary,
            expected_audit_summary,
            expected_courses,
            get_course_url_mock,
            get_course_runs_mock
    ):
        get_course_url_mock.return_value = ''
        get_course_runs_mock.return_value = course_runs
        course_exporter = SapCourseExporter(self.user, self.plugin_configuration)

        audit_summary = course_exporter.resolve_removed_courses(previous_audit_summary)
        assert audit_summary == expected_audit_summary
        assert course_exporter.removed_courses_resolved
        assert course_exporter.courses == expected_courses

        second_audit_summary = course_exporter.resolve_removed_courses(previous_audit_summary)
        assert second_audit_summary == {}

    @ddt.data(
        (
            {
                'mode': 'enroll',
                'number': 0,
            },
            {
                'mode': 'audit',
                'number': 1,
            },
            {
                'mode': 'another_audit',
                'number': 2,
            },
            {
                'mode': 'enroll',
                'number': 3,
            },
            {
                'mode': 'audit',
                'number': 4,
            },
        )
    )
    @override_settings(ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES=['audit', 'another_audit'])
    def test_filter_audit_course_modes(
            self,
            course_modes,
    ):
        # when the audit enrollment flag is disabled
        self.customer.enable_audit_enrollment = False
        # course modes are filtered out if their mode is in the ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES setting
        filtered_course_modes = filter_audit_course_modes(self.customer, course_modes)
        assert len(filtered_course_modes) == 2
        result = [course_mode['number'] for course_mode in filtered_course_modes]
        expected = [0, 3]
        self.assertListEqual(result, expected)

        # when the audit enrollment flag is enabled
        self.customer.enable_audit_enrollment = True
        # audit course modes are not filtered out
        filtered_course_modes = filter_audit_course_modes(self.customer, course_modes)
        assert len(filtered_course_modes) == 5

    @mock.patch('integrated_channels.sap_success_factors.utils.configuration_helpers')
    @mock.patch('enterprise.models.configuration_helpers')
    def test_get_launch_url_flag_on(
            self,
            mock_config_helpers_1,
            mock_config_helpers_2):
        """
        Test `get_launch_url` helper method.
        """
        mock_config_helpers_1.get_value.return_value = 'https://www.example.com'
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_uuid = '47432370-0a6e-4d95-90fe-77b4fe64de2c'
        expected_url = ('https://www.example.com/enterprise/47432370-0a6e-4d95-90fe-77b4fe64de2c/course/'
                        'course-v1:edX+DemoX+Demo_Course/enroll/')
        enterprise_customer = EnterpriseCustomerFactory(uuid=enterprise_uuid)
        mock_config_helpers_2.get_value.return_value = 1

        launch_url = get_launch_url(enterprise_customer, course_id)
        assert launch_url == expected_url

    @mock.patch('integrated_channels.sap_success_factors.utils.reverse')
    def test_get_launch_url_flag_off(
            self,
            reverse_mock):
        """
        Test `get_launch_url` helper method.
        """
        reverse_mock.return_value = '/course_modes/choose/course-v1:edX+DemoX+Demo_Course/'
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_uuid = '37432370-0a6e-4d95-90fe-77b4fe64de2d'
        expected_url = 'https://example.com/course_modes/choose/course-v1:edX+DemoX+Demo_Course/'
        enterprise_customer = EnterpriseCustomerFactory(
            site=SiteFactory(domain='example.com'),
            uuid=enterprise_uuid
        )

        launch_url = get_launch_url(enterprise_customer, course_id)
        assert launch_url == expected_url
