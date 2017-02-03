# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""
from __future__ import absolute_import, unicode_literals

import datetime
from operator import itemgetter

import ddt
from rest_framework.reverse import reverse

from django.conf import settings
from django.test import override_settings

from enterprise.models import EnterpriseCustomer, UserDataSharingConsentAudit
from test_utils import TEST_USERNAME, APITest, factories


@ddt.ddt
class TestEnterpriseAPIViews(APITest):
    """
    Tests for enterprise api views.
    """
    # Get current datetime, so that all tests can use same datetime.
    now = datetime.datetime.now()

    def create_items(self, factory, items):
        """
        Create model instances using given factory
        """
        for item in items:
            factory.create(**item)

    @ddt.data(
        (
            factories.UserFactory,
            reverse('auth-user-list'),
            itemgetter('username'),
            [
                {
                    'username': 'test_user_1',
                    'first_name': 'Test 1',
                    'last_name': 'User',
                    'email': 'test1@example.com',
                    'is_staff': True,
                    'is_active': False,
                    'date_joined': now - datetime.timedelta(days=10),
                },
                {
                    'username': 'test_user_2',
                    'first_name': 'Test 2',
                    'last_name': 'User',
                    'email': 'test2@example.com',
                    'is_staff': False,
                    'is_active': True,
                    'date_joined': now - datetime.timedelta(days=20),
                },
            ],
            [
                {
                    'username': 'test_user_1',
                    'first_name': 'Test 1',
                    'last_name': 'User',
                    'email': 'test1@example.com',
                    'is_staff': True,
                    'is_active': False,
                    'date_joined': (now - datetime.timedelta(days=10)).isoformat(),
                },
                {
                    'username': 'test_user_2',
                    'first_name': 'Test 2',
                    'last_name': 'User',
                    'email': 'test2@example.com',
                    'is_staff': False,
                    'is_active': True,
                    'date_joined': (now - datetime.timedelta(days=20)).isoformat(),
                },
            ],
        ),
    )
    @ddt.unpack
    def test_user_view(self, factory, url, sorting_key, model_items, expected_json):
        """
        Make sure API end point 'user' returns all of the expected fields.
        """
        self.create_items(factory, model_items)
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)

        # We need to account for the user created in setUp
        expected_json.append({
            'username': self.user.username,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'email': self.user.email,
            'is_staff': self.user.is_staff,
            'is_active': self.user.is_active,
            'date_joined': self.user.date_joined.isoformat(),
        })

        for user in response['results']:
            user.pop('id', None)

        assert sorted(expected_json, key=sorting_key) == sorted(response['results'], key=sorting_key)

    @ddt.data(
        (
            factories.SiteFactory,
            reverse('site-list'),
            itemgetter('domain'),
            [{'domain': 'example.com', 'name': 'example.com'}],
            [{'domain': 'example.com', 'name': 'example.com'}],
        ),
        (
            factories.EnterpriseCustomerBrandingFactory,
            reverse('enterprise-customer-branding-list'),
            itemgetter('enterprise_customer'),
            [{
                'enterprise_customer__uuid': 'd1098bfb-2c78-44f1-9eb2-b94475356a3f',
                'logo': '/static/images/logo.png'
            }],
            [{
                'enterprise_customer': 'd1098bfb-2c78-44f1-9eb2-b94475356a3f',
                'logo': settings.TEST_SERVER + settings.MEDIA_URL + 'static/images/logo.png'
            }],
        ),
        (
            factories.EnterpriseCustomerFactory,
            reverse('enterprise-customer-list'),
            itemgetter('uuid'),
            [{
                'uuid': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_login',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }],
            [{
                'uuid': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_login', 'enterprise_customer_users': [],
                'branding_configuration': None, 'enterprise_customer_entitlements': [],
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
            }],
        ),
        (
            factories.UserDataSharingConsentAuditFactory,
            reverse('user-data-sharing-consent-list'),
            itemgetter('user'),
            [{
                'state': 'enabled',
                'user__id': 1,
            }],
            [{
                'state': 'enabled', 'enabled': True, 'user': 1,
            }],
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            reverse('enterprise-learner-list'),
            itemgetter('user_id'),
            [{
                'id': 1, 'user_id': 0,
                'enterprise_customer__uuid': 'd3098bfb-2c78-44f1-9eb2-b94475356a3f',
                'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_login',
                'enterprise_customer__site__domain': 'example.com', 'enterprise_customer__site__name': 'example.com',

            }],
            [{
                'id': 1, 'user_id': 0, 'user': None, 'data_sharing_consent': [],
                'enterprise_customer': {
                    'uuid': 'd3098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                    'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_login', 'enterprise_customer_users': [1],
                    'branding_configuration': None, 'enterprise_customer_entitlements': [],
                    'site': {
                        'domain': 'example.com', 'name': 'example.com'
                    },
                }
            }],
        ),
        (
            factories.EnterpriseCustomerEntitlementFactory,
            reverse('enterprise-customer-entitlement-list'),
            itemgetter('enterprise_customer'),
            [{
                'enterprise_customer__uuid': 'd1098bfb-2c78-44f1-9eb2-b94475356a3f',
                'entitlement_id': 1
            }],
            [{
                'enterprise_customer': 'd1098bfb-2c78-44f1-9eb2-b94475356a3f',
                'entitlement_id': 1
            }],
        ),
        (
            factories.EnterpriseCourseEnrollmentFactory,
            reverse('enterprise-course-enrollment-list'),
            itemgetter('enterprise_customer_user'),
            [{
                'enterprise_customer_user__id': 1,
                'consent_granted': True,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            }],
            [{
                'enterprise_customer_user': 1,
                'consent_granted': True,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            }],
        )
    )
    @ddt.unpack
    def test_api_views(self, factory, url, sorting_key, model_items, expected_json):
        """
        Make sure API end point returns all of the expected fields.
        """
        self.create_items(factory, model_items)
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)

        assert sorted(expected_json, key=sorting_key) == sorted(response['results'], key=sorting_key)

    @ddt.data(
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3],
            {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": True},
                {"entitlement_id": 2, "requires_consent": True},
                {"entitlement_id": 3, "requires_consent": True},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": True},
                {"entitlement_id": 2, "requires_consent": True},
                {"entitlement_id": 3, "requires_consent": True},
            ]},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET,
            [], {"entitlements": []},
        ),
    )
    @ddt.unpack
    def test_enterprise_learner_entitlements(
            self, enable_data_sharing_consent, enforce_data_sharing_consent,
            learner_consent_state, entitlements, expected_json
    ):
        """
        Test that entitlement details route on enterprise learner returns correct data.

        This test verifies that entitlements returned by entitlement details route on enterprise learner
        has the expected behavior as listed down.
            1. Empty entitlements list if enterprise customer requires data sharing consent
                (this includes enforcing data sharing consent at login and at enrollment) and enterprise learner
                 does not consent to share data.
            2. Full list of entitlements for all other cases.

        Arguments:
            enable_data_sharing_consent (bool): True if enterprise customer enables data sharing consent,
                False it does not.
            enforce_data_sharing_consent (str): string for the location at which enterprise customer enforces
                data sharing consent, possible values are 'at_login', 'at_enrollment' and 'optional'.
            learner_consent_state (str): string containing the state of learner consent on data sharing,
                possible values are 'not_set', 'enabled' and 'disabled'.
            entitlements (list): A list of integers pointing to voucher ids generated in E-Commerce CAT tool.
            expected_json (dict): A dict with structure and values corresponding to
                the expected json from API endpoint.
        """
        user_id = 1
        enterprise_customer = factories.EnterpriseCustomerFactory(
            enable_data_sharing_consent=enable_data_sharing_consent,
            enforce_data_sharing_consent=enforce_data_sharing_consent,
        )
        factories.UserDataSharingConsentAuditFactory(
            user__id=user_id,
            user__enterprise_customer=enterprise_customer,
            state=learner_consent_state,
        )
        for entitlement in entitlements:
            factories.EnterpriseCustomerEntitlementFactory(
                enterprise_customer=enterprise_customer,
                entitlement_id=entitlement,
            )
        url = reverse('enterprise-learner-entitlements', (user_id, ))
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)
        assert sorted(response) == sorted(expected_json)

    @override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME=TEST_USERNAME)
    @ddt.data(
        (
            # Test a valid request
            [
                factories.EnterpriseCustomerUserFactory,
                [{
                    'id': 1, 'user_id': 0,
                    'enterprise_customer__uuid': 'd3098bfb-2c78-44f1-9eb2-b94475356a3f',
                    'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                    'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                    'enterprise_customer__enforce_data_sharing_consent': 'at_login',
                    'enterprise_customer__site__domain': 'example.com',
                    'enterprise_customer__site__name': 'example.com',
                }]
            ],
            {
                'username': TEST_USERNAME,
                'consent_granted': True,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            201
        ),
        (
            # Test a bad request due to an invalid user
            [
                factories.EnterpriseCustomerUserFactory,
                [{
                    'id': 1, 'user_id': 0,
                    'enterprise_customer__uuid': 'd3098bfb-2c78-44f1-9eb2-b94475356a3f',
                    'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                    'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                    'enterprise_customer__enforce_data_sharing_consent': 'at_login',
                    'enterprise_customer__site__domain': 'example.com',
                    'enterprise_customer__site__name': 'example.com',
                }]
            ],
            {
                'username': 'does_not_exist',
                'consent_granted': True,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            400
        ),
        (
            # Test a bad request due to no existing EnterpriseCustomerUser
            [
                factories.EnterpriseCustomerFactory,
                [{
                    'uuid': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                    'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_login',
                    'site__domain': 'example.com', 'site__name': 'example.com',
                }]
            ],
            {
                'username': TEST_USERNAME,
                'consent_granted': True,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            400
        )
    )
    @ddt.unpack
    def test_post_enterprise_course_enrollment(self, factory, request_data, status_code):
        """
        Make sure service users can post new EnterpriseCourseEnrollments.
        """
        factory_type, factory_data = factory
        if factory_type == factories.EnterpriseCustomerUserFactory:
            factory_data[0]['user_id'] = self.user.pk  # pylint: disable=no-member

        self.create_items(*factory)

        response = self.client.post(
            settings.TEST_SERVER + reverse('enterprise-course-enrollment-list'),
            data=request_data
        )

        assert response.status_code == status_code
        response = self.load_json(response.content)

        if status_code == 200:
            self.assertDictEqual(request_data, response)

    @override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME=TEST_USERNAME)
    @ddt.data(
        (TEST_USERNAME, 201),
        ('does_not_exist', 400)
    )
    @ddt.unpack
    def test_post_enterprise_customer_user(self, username, status_code):
        """
        Make sure service users can post new EnterpriseCustomerUsers.
        """
        self.create_items(
            factories.EnterpriseCustomerFactory,
            [{
                'uuid': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_login',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }]
        )
        data = {
            'enterprise_customer': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f',
            'username': username,
        }
        response = self.client.post(settings.TEST_SERVER + reverse('enterprise-learner-list'), data=data)

        assert response.status_code == status_code
        response = self.load_json(response.content)

        if status_code == 200:
            self.assertDictEqual(data, response)

    def test_post_enterprise_customer_user_logged_out(self):
        """
        Make sure users can't post EnterpriseCustomerUsers when logged out.
        """
        self.client.logout()
        self.create_items(
            factories.EnterpriseCustomerFactory,
            [{
                'uuid': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f', 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_login',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }]
        )
        data = {
            'enterprise_customer': 'd2098bfb-2c78-44f1-9eb2-b94475356a3f',
            'username': self.user.username
        }
        response = self.client.post(settings.TEST_SERVER + reverse('enterprise-learner-list'), data=data)
        assert response.status_code == 401
