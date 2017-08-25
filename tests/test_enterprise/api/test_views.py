# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""
from __future__ import absolute_import, unicode_literals

import datetime
from operator import itemgetter

import ddt
import mock
from rest_framework.reverse import reverse

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from enterprise.api_client.lms import LMS_API_DATETIME_FORMAT
from enterprise.decorators import ignore_warning
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerIdentityProvider, UserDataSharingConsentAudit
from test_utils import FAKE_UUIDS, TEST_USERNAME, APITest, factories, fake_catalog_api

AUTH_USER_LIST_ENDPOINT = reverse('auth-user-list')
CATALOGS_LIST_ENDPOINT = reverse('catalogs-list')
CATALOGS_DETAIL_ENDPOINT = reverse('catalogs-detail', (1, ))
CATALOGS_COURSES_ENDPOINT = reverse('catalogs-courses', (1, ))
ENTERPRISE_CATALOGS_LIST_ENDPOINT = reverse('enterprise-catalogs-list')
ENTERPRISE_CATALOGS_DETAIL_ENDPOINT = reverse('enterprise-catalogs-detail', (FAKE_UUIDS[1],))
ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT = reverse('enterprise-course-enrollment-list')
ENTERPRISE_CUSTOMER_CATALOG_LIST_ENDPOINT = reverse('enterprise-customer-catalog-list')
ENTERPRISE_CUSTOMER_COURSES_ENDPOINT = reverse('enterprise-customer-courses', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_ENTITLEMENT_LIST_ENDPOINT = reverse('enterprise-customer-entitlement-list')
ENTERPRISE_CUSTOMER_LIST_ENDPOINT = reverse('enterprise-customer-list')
ENTERPRISE_LEARNER_LIST_ENDPOINT = reverse('enterprise-learner-list')
PROGRAMS_DETAIL_ENDPOINT = reverse('programs-detail', (FAKE_UUIDS[3],))
SITE_LIST_ENDPOINT = reverse('site-list')
USER_DATA_SHARING_CONSENT_LIST_ENDPOINT = reverse('user-data-sharing-consent-list')


@ddt.ddt
class TestEnterpriseAPIViews(APITest):
    """
    Tests for enterprise api views.
    """
    # Get current datetime, so that all tests can use same datetime.
    now = timezone.now()

    def create_items(self, factory, items):
        """
        Create model instances using given factory
        """
        for item in items:
            factory.create(**item)

    @ddt.data(
        (
            factories.UserFactory,
            AUTH_USER_LIST_ENDPOINT,
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
                    'date_joined': (now - datetime.timedelta(days=10)).strftime(LMS_API_DATETIME_FORMAT),
                },
                {
                    'username': 'test_user_2',
                    'first_name': 'Test 2',
                    'last_name': 'User',
                    'email': 'test2@example.com',
                    'is_staff': False,
                    'is_active': True,
                    'date_joined': (now - datetime.timedelta(days=20)).strftime(LMS_API_DATETIME_FORMAT),
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
            'date_joined': self.user.date_joined.strftime(LMS_API_DATETIME_FORMAT),
        })

        for user in response['results']:
            user.pop('id', None)

        assert sorted(expected_json, key=sorting_key) == sorted(response['results'], key=sorting_key)

    @ddt.data(
        (
            factories.SiteFactory,
            SITE_LIST_ENDPOINT,
            itemgetter('domain'),
            [{'domain': 'example.com', 'name': 'example.com'}],
            [{'domain': 'example.com', 'name': 'example.com'}],
        ),
        (
            factories.EnterpriseCustomerFactory,
            ENTERPRISE_CUSTOMER_LIST_ENDPOINT,
            itemgetter('uuid'),
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }],
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment', 'enterprise_customer_users': [],
                'branding_configuration': None, 'enterprise_customer_entitlements': [],
                'enable_audit_enrollment': False,
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
            }],
        ),
        (
            factories.UserDataSharingConsentAuditFactory,
            USER_DATA_SHARING_CONSENT_LIST_ENDPOINT,
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
            ENTERPRISE_LEARNER_LIST_ENDPOINT,
            itemgetter('user_id'),
            [{
                'id': 1, 'user_id': 0,
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com', 'enterprise_customer__site__name': 'example.com',

            }],
            [{
                'id': 1, 'user_id': 0, 'user': None, 'data_sharing_consent': [],
                'enterprise_customer': {
                    'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                    'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_enrollment', 'enterprise_customer_users': [1],
                    'branding_configuration': None, 'enterprise_customer_entitlements': [],
                    'enable_audit_enrollment': False,
                    'site': {
                        'domain': 'example.com', 'name': 'example.com'
                    },
                }
            }],
        ),
        (
            factories.EnterpriseCustomerEntitlementFactory,
            ENTERPRISE_CUSTOMER_ENTITLEMENT_LIST_ENDPOINT,
            itemgetter('enterprise_customer'),
            [{
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'entitlement_id': 1
            }],
            [{
                'enterprise_customer': FAKE_UUIDS[0],
                'entitlement_id': 1
            }],
        ),
        (
            factories.EnterpriseCourseEnrollmentFactory,
            ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT,
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
        ),
        (
            factories.EnterpriseCustomerCatalogFactory,
            ENTERPRISE_CUSTOMER_CATALOG_LIST_ENDPOINT,
            itemgetter('enterprise_customer'),
            [{
                'uuid': FAKE_UUIDS[0],
                'enterprise_customer__uuid': FAKE_UUIDS[1],
                'query': 'querystring',
            }],
            [{
                'uuid': FAKE_UUIDS[0],
                'enterprise_customer': FAKE_UUIDS[1],
                'query': 'querystring',
            }]
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
            True, EnterpriseCustomer.EXTERNALLY_MANAGED, UserDataSharingConsentAudit.EXTERNALLY_MANAGED,
            [1, 2, 3],
            {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
    )
    @ddt.unpack
    @ignore_warning(DeprecationWarning)
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
                data sharing consent, possible values are 'at_enrollment' and 'externally_managed'.
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
                    'enterprise_customer__uuid': FAKE_UUIDS[0],
                    'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                    'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                    'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
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
                    'enterprise_customer__uuid': FAKE_UUIDS[0],
                    'enterprise_customer__name': 'Test Enterprise Customer', 'enterprise_customer__catalog': 1,
                    'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                    'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
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
                    'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                    'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_enrollment',
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
            settings.TEST_SERVER + ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT,
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
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }]
        )
        data = {
            'enterprise_customer': FAKE_UUIDS[0],
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
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }]
        )
        data = {
            'enterprise_customer': FAKE_UUIDS[0],
            'username': self.user.username
        }
        response = self.client.post(settings.TEST_SERVER + reverse('enterprise-learner-list'), data=data)
        assert response.status_code == 401

    @ddt.data(
        (
            FAKE_UUIDS[0],
            None,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            True,
            {},
            {'detail': (
                "No catalog is associated with Enterprise Pied Piper from endpoint "
                "'/enterprise/api/v1/enterprise-customer/" + FAKE_UUIDS[0] + "/courses/'."
            )}
        ),
        (
            FAKE_UUIDS[0],
            1,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            False,
            {},
            {'detail': 'User must be a staff user or associated with the specified Enterprise.'}
        ),
        (
            FAKE_UUIDS[0],
            1,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            True,
            {},
            {'detail': (
                "Unable to fetch API response for catalog courses for Enterprise Pied Piper from endpoint "
                "'/enterprise/api/v1/enterprise-customer/" + FAKE_UUIDS[0] + "/courses/'."
            )},
        ),
        (
            FAKE_UUIDS[0],
            1,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            True,
            fake_catalog_api.FAKE_CATALOG_COURSE_PAGINATED_RESPONSE,
            {
                'count': 3,
                'next': ('http://testserver/enterprise/api/v1/enterprise-customer/'
                         + FAKE_UUIDS[0] + '/courses/?page=3'),
                'previous': ('http://testserver/enterprise/api/v1/enterprise-customer/'
                             + FAKE_UUIDS[0] + '/courses/?page=1'),
                'results': [
                    {
                        'owners': [
                            {
                                'description': None,
                                'tags': [],
                                'name': '',
                                'homepage_url': None,
                                'key': 'edX',
                                'certificate_logo_image_url': None,
                                'marketing_url': None,
                                'logo_image_url': None,
                                'uuid': FAKE_UUIDS[1]
                            }
                        ],
                        'tpa_hint': None,
                        'catalog_id': 1,
                        'enterprise_id': FAKE_UUIDS[0],
                        'uuid': FAKE_UUIDS[2],
                        'title': 'edX Demonstration Course',
                        'prerequisites': [],
                        'image': None,
                        'expected_learning_items': [],
                        'sponsors': [],
                        'modified': '2017-03-03T07:34:19.322916Z',
                        'full_description': None,
                        'subjects': [],
                        'video': None,
                        'key': 'edX+DemoX',
                        'short_description': None,
                        'marketing_url': None,
                        'level_type': None,
                        'course_runs': []
                    }
                ]
            }
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.CourseCatalogApiClient')
    def test_enterprise_customer_courses(
            self,
            enterprise_uuid,
            catalog,
            url,
            link_user,
            mocked_catalog_courses,
            expected,
            mock_catalog_api_client
    ):
        """
        Make sure the enterprise courses view returns correct data.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=enterprise_uuid,
            catalog=catalog,
            name='Pied Piper',
        )

        if link_user:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer,
            )

            EnterpriseCustomerIdentityProvider(
                enterprise_customer=enterprise_customer,
                provider_id='saml-testshib',
            )

        mock_catalog_api_client.return_value = mock.Mock(
            get_paginated_catalog_courses=mock.Mock(return_value=mocked_catalog_courses),
        )
        response = self.client.get(url)
        response = self.load_json(response.content)

        assert response == expected

    @ddt.data(
        (
            ENTERPRISE_CATALOGS_DETAIL_ENDPOINT,
            False,
            False,
            '',
            {
                'detail': "User must be a staff user or "
                          "associated with the endpoint's appointed common Enterprise Customer."
            },
        ),
        (
            ENTERPRISE_CATALOGS_DETAIL_ENDPOINT,
            False,
            True,
            '',
            fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
        ),
        (
            ENTERPRISE_CATALOGS_DETAIL_ENDPOINT,
            True,
            False,
            'no catalog for query so endpoint should return all results',
            fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
        ),
        (
            ENTERPRISE_CATALOGS_DETAIL_ENDPOINT,
            True,
            True,
            '',
            fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
        ),
        (
            ENTERPRISE_CATALOGS_DETAIL_ENDPOINT,
            True,
            True,
            'edX Demonstration Course',
            {
                'count': 2,
                'next': None,
                'previous': None,
                'results': [
                    fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT,
                    fake_catalog_api.FAKE_SEARCH_ALL_SHORT_COURSE_RESULT,
                ],
            },
        ),
        (
            PROGRAMS_DETAIL_ENDPOINT,
            True,
            True,
            'uses programs uuid from query parameters for search for programs endpoint',
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT],
            },
        ),
    )
    @ddt.unpack
    def test_enterprise_customer_catalogs_detail(self, url, is_staff, has_existing_catalog, querystring,
                                                 expected_search_results):
        """
        Make sure the Enterprise Customer's Catalog view correctly returns details about specific catalogs based on
        ``querystring``.

        Search results should also take into account whether

        * requesting user is staff.
        * enterprise customer has a catalog associated with it.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0]
        )
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if has_existing_catalog:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
            factories.EnterpriseCustomerCatalogFactory(
                uuid=FAKE_UUIDS[1],
                enterprise_customer=enterprise_customer,
                query=querystring
            )
        with mock.patch('enterprise.api.v1.views.CourseCatalogApiClient') as mock_catalog_api_client:
            mock_catalog_api_client.return_value = mock.Mock(
                get_paginated_search_results=mock.Mock(
                    side_effect=fake_catalog_api.get_paginated_search_results
                ),
            )
            response = self.client.get(url)
            response = self.load_json(response.content)

            assert response == expected_search_results

    @ddt.data(
        (
            ENTERPRISE_CATALOGS_LIST_ENDPOINT,
            False,
            False,
            {},
            {'detail': "User must be a staff user or "
                       "associated with the endpoint's appointed common Enterprise Customer."},
        ),
        (
            ENTERPRISE_CATALOGS_LIST_ENDPOINT,
            False,
            True,
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
        ),
        (
            ENTERPRISE_CATALOGS_LIST_ENDPOINT,
            True,
            False,
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
        ),
        (
            ENTERPRISE_CATALOGS_LIST_ENDPOINT,
            True,
            True,
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page=3&page_size=1',
                'previous': 'http://testserver/enterprise/api/v1/enterprise-catalogs/?page_size=1',
                'results': [fake_catalog_api.FAKE_SEARCH_ALL_COURSE_RESULT],
            },
        ),
    )
    @ddt.unpack
    def test_enterprise_customer_catalogs_list(self, url, is_staff, has_existing_catalog, mocked_search_results,
                                               expected_catalogs):
        """
        Make sure the Enterprise Customer's Catalog view returns correctly paginated data.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0]
        )
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if has_existing_catalog:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
            factories.EnterpriseCustomerCatalogFactory(
                uuid=FAKE_UUIDS[1],
                enterprise_customer=enterprise_customer,
                query=''
            )
        with mock.patch('enterprise.api.v1.views.CourseCatalogApiClient') as mock_catalog_api_client:
            mock_catalog_api_client.return_value = mock.Mock(
                get_paginated_search_results=mock.Mock(return_value=mocked_search_results),
            )
            response = self.client.get(url)
            response = self.load_json(response.content)

            assert response == expected_catalogs

    @ddt.data(
        (
            CATALOGS_LIST_ENDPOINT,
            {},
            {'detail': "Unable to fetch API response from endpoint '{}'.".format(CATALOGS_LIST_ENDPOINT)},
        ),
        (
            CATALOGS_LIST_ENDPOINT,
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/catalogs/?page=3',
                'previous': 'http://testserver/enterprise/api/v1/catalogs/?page=1',
                'results':
                    [
                        {
                            'id': 2,
                            'name': 'Enterprise All Biology',
                            'query': 'title:*Biology*',
                            'courses_count': 3,
                            'viewers': []
                        },
                    ]
            },
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/catalogs/?page=3',
                'previous': 'http://testserver/enterprise/api/v1/catalogs/?page=1',
                'results':
                    [
                        {
                            'id': 2,
                            'name': 'Enterprise All Biology',
                            'query': 'title:*Biology*',
                            'courses_count': 3,
                            'viewers': []
                        },
                    ]
            },
        )
    )
    @ddt.unpack
    def test_enterprise_catalogs_list(self, url, mocked_catalogs, expected_catalogs):
        """
        Make sure enterprise catalog view returns correct data.
        Arguments:
            mocked_catalogs (dict): A dict containing catalog information as returned by discovery API.
            expected_catalogs (dict): A dict elements containing expected catalog information.
        """
        with mock.patch('enterprise.api.v1.views.CourseCatalogApiClient') as mock_catalog_api_client:
            mock_catalog_api_client.return_value = mock.Mock(
                get_paginated_catalogs=mock.Mock(return_value=mocked_catalogs),
            )
            response = self.client.get(url)
            response = self.load_json(response.content)

            assert response == expected_catalogs

    @ddt.data(
        (
            CATALOGS_DETAIL_ENDPOINT,
            {},
            {'detail': "Unable to fetch API response for given catalog from endpoint '/catalog/1/'. "
                       "The resource you are looking for does not exist."},
        ),
        (
            CATALOGS_DETAIL_ENDPOINT,
            {
                'id': 1,
                'name': 'Enterprise Dummy Catalog',
                'query': '*',
                'courses_count': 22,
                'viewers': []
            },
            {
                'id': 1,
                'name': 'Enterprise Dummy Catalog',
                'query': '*',
                'courses_count': 22,
                'viewers': []
            },
        ),
    )
    @ddt.unpack
    def test_enterprise_catalog_details(self, url, mocked_catalog, expected):
        """
        Make sure enterprise catalog view returns correct data.
        Arguments:
            mocked_catalog (dict): This is used to mock catalog returned by catalog api.
            expected (list): This is the expected catalog from enterprise api.
        """
        with mock.patch('enterprise.api.v1.views.CourseCatalogApiClient') as mock_catalog_api_client:
            mock_catalog_api_client.return_value = mock.Mock(
                get_catalog=mock.Mock(return_value=mocked_catalog),
            )
            response = self.client.get(url)
            response = self.load_json(response.content)

            assert response == expected

    @ddt.data(
        (
            CATALOGS_COURSES_ENDPOINT,
            'saml-testshib',
            FAKE_UUIDS[0],
            {},
            {'detail': "Unable to fetch API response for catalog courses from endpoint "
                       "'/enterprise/api/v1/catalogs/1/courses/'. The resource you are looking for does not exist."},
        ),
        (
            CATALOGS_COURSES_ENDPOINT,
            'saml-testshib',
            FAKE_UUIDS[0],
            fake_catalog_api.FAKE_CATALOG_COURSE_PAGINATED_RESPONSE,
            {
                'count': 3,
                'next': 'http://testserver/enterprise/api/v1/catalogs/1/courses/?page=3',
                'previous': 'http://testserver/enterprise/api/v1/catalogs/1/courses/?page=1',
                'results': [
                    {
                        'owners': [
                            {
                                'description': None,
                                'tags': [],
                                'name': '',
                                'homepage_url': None,
                                'key': 'edX',
                                'certificate_logo_image_url': None,
                                'marketing_url': None,
                                'logo_image_url': None,
                                'uuid': FAKE_UUIDS[1]
                            }
                        ],
                        'tpa_hint': 'saml-testshib',
                        'catalog_id': '1',
                        'enterprise_id': FAKE_UUIDS[0],
                        'uuid': FAKE_UUIDS[2],
                        'title': 'edX Demonstration Course',
                        'prerequisites': [],
                        'image': None,
                        'expected_learning_items': [],
                        'sponsors': [],
                        'modified': '2017-03-03T07:34:19.322916Z',
                        'full_description': None,
                        'subjects': [],
                        'video': None,
                        'key': 'edX+DemoX',
                        'short_description': None,
                        'marketing_url': None,
                        'level_type': None,
                        'course_runs': []
                    }
                ]
            },
        ),
    )
    @ddt.unpack
    def test_enterprise_catalog_courses(self, url, provider_id, enterprise_customer, mocked_catalog_courses, expected):
        """
        Make sure enterprise catalog view returns correct data.
        Arguments:
            mocked_catalog_courses: This is used to mock catalog courses returned by catalog api.
            expected: This is the expected catalog courses from enterprise api.
        """
        # Populate database
        ecu = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer__uuid=enterprise_customer,
        )

        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=ecu.enterprise_customer,
            provider_id=provider_id,
        )

        with mock.patch('enterprise.api.v1.views.CourseCatalogApiClient') as mock_catalog_api_client:
            mock_catalog_api_client.return_value = mock.Mock(
                get_paginated_catalog_courses=mock.Mock(return_value=mocked_catalog_courses),
            )
            response = self.client.get(url)
            response = self.load_json(response.content)

            assert response == expected

    def test_enterprise_catalog_courses_unauthorized(self):
        """
        Make sure enterprise catalog view returns correct data.
        Arguments:
            mocked_catalog_courses: This is used to mock catalog courses returned by catalog api.
            expected: This is the expected catalog courses from enterprise api.
        """
        response = self.client.get(CATALOGS_COURSES_ENDPOINT)
        response_content = self.load_json(response.content)

        assert response.status_code == 403
        assert response_content['detail'] == 'User {username} is not associated with an EnterpriseCustomer.'.format(
            username=self.user.username
        )
