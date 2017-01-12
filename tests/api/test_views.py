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

from test_utils import APITest, factories


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
            reverse('user-list'),
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
                'user_id': 0, 'user': None, 'data_sharing_consent': [],
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

    )
    @ddt.unpack
    def test_api_views(self, factory, url, sorting_key, model_items, expected_json):
        """
        Make sure API end point returns all of the expected fields.
        """
        self.create_items(factory, model_items)
        # import pdb; pdb.set_trace()
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)

        assert sorted(expected_json, key=sorting_key) == sorted(response['results'], key=sorting_key)
