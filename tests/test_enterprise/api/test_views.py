# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""
from __future__ import absolute_import, unicode_literals

import json
from operator import itemgetter

import ddt
import mock
from pytest import mark
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from six.moves.urllib.parse import (  # pylint: disable=import-error,ungrouped-imports
    parse_qs,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.utils import timezone

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from test_utils import (
    FAKE_UUIDS,
    TEST_COURSE,
    TEST_COURSE_KEY,
    TEST_PASSWORD,
    TEST_SLUG,
    TEST_USERNAME,
    APITest,
    factories,
    fake_catalog_api,
    fake_enterprise_api,
    update_course_run_with_enterprise_context,
    update_course_with_enterprise_context,
    update_program_with_enterprise_context,
)

CATALOGS_LIST_ENDPOINT = reverse('catalogs-list')
CATALOGS_DETAIL_ENDPOINT = reverse('catalogs-detail', (1, ))
CATALOGS_COURSES_ENDPOINT = reverse('catalogs-courses', (1, ))
ENTERPRISE_CATALOGS_LIST_ENDPOINT = reverse('enterprise-catalogs-list')
ENTERPRISE_CATALOGS_DETAIL_ENDPOINT = reverse(
    'enterprise-catalogs-detail',
    kwargs={'pk': FAKE_UUIDS[1]}
)
ENTERPRISE_CATALOGS_CONTAINS_CONTENT_ENDPOINT = reverse(
    'enterprise-catalogs-contains-content-items',
    kwargs={'pk': FAKE_UUIDS[1]}
)
ENTERPRISE_CATALOGS_COURSE_ENDPOINT = reverse(
    # pylint: disable=anomalous-backslash-in-string
    r'enterprise-catalogs-courses/(?P<course-key>[^/+]+(/|\+)[^/+]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'course_key': TEST_COURSE_KEY}
)
ENTERPRISE_CATALOGS_COURSE_RUN_ENDPOINT = reverse(
    # pylint: disable=anomalous-backslash-in-string
    r'enterprise-catalogs-course-runs/(?P<course-id>[^/+]+(/|\+)[^/+]+(/|\+)[^/?]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'course_id': TEST_COURSE}
)
ENTERPRISE_CATALOGS_PROGRAM_ENDPOINT = reverse(
    r'enterprise-catalogs-programs/(?P<program-uuid>[^/]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'program_uuid': FAKE_UUIDS[3]}
)
ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT = reverse('enterprise-course-enrollment-list')
ENTERPRISE_CUSTOMER_COURSES_ENDPOINT = reverse('enterprise-customer-courses', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_ENTITLEMENT_LIST_ENDPOINT = reverse('enterprise-customer-entitlement-list')
ENTERPRISE_CUSTOMER_BRANDING_LIST_ENDPOINT = reverse('enterprise-customer-branding-list')
ENTERPRISE_CUSTOMER_BRANDING_DETAIL_ENDPOINT = reverse('enterprise-customer-branding-detail', (TEST_SLUG,))
ENTERPRISE_CUSTOMER_LIST_ENDPOINT = reverse('enterprise-customer-list')
ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT = reverse(
    'enterprise-customer-contains-content-items',
    kwargs={'pk': FAKE_UUIDS[0]}
)
ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT = reverse('enterprise-customer-course-enrollments', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_REPORTING_ENDPOINT = reverse('enterprise-customer-reporting-list')
ENTERPRISE_LEARNER_ENTITLEMENTS_ENDPOINT = reverse('enterprise-learner-entitlements', (1,))
ENTERPRISE_LEARNER_LIST_ENDPOINT = reverse('enterprise-learner-list')
ENTERPRISE_CUSTOMER_WITH_ACCESS_TO_ENDPOINT = reverse('enterprise-customer-with-access-to')


def side_effect(url, query_parameters):
    """
    returns a url with updated query parameters.
    """
    if any(key in ['utm_medium', 'catalog'] for key in query_parameters):
        return url

    scheme, netloc, path, query_string, fragment = urlsplit(url)
    url_params = parse_qs(query_string)

    # Update url query parameters
    url_params.update(query_parameters)

    return urlunsplit(
        (scheme, netloc, path, urlencode(url_params, doseq=True), fragment),
    )


@ddt.ddt
@mark.django_db
class TestEnterpriseAPIViews(APITest):
    """
    Tests for enterprise api views.
    """
    # Get current datetime, so that all tests can use same datetime.
    now = timezone.now()
    maxDiff = None

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=True, **kwargs)
        self.user.set_password(password)  # pylint: disable=no-member
        self.user.save()  # pylint: disable=no-member

    def create_items(self, factory, items):
        """
        Create model instances using given factory
        """
        for item in items:
            factory.create(**item)

    @ddt.data(
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, True,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, False,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": True},
                {"entitlement_id": 2, "requires_consent": True},
                {"entitlement_id": 3, "requires_consent": True},
            ]},
        ),
        (
            False, EnterpriseCustomer.AT_ENROLLMENT, True,
            [1, 2, 3], {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
        ),
        (
            True, EnterpriseCustomer.AT_ENROLLMENT, None,
            [], {"entitlements": []},
        ),
        (
            True, EnterpriseCustomer.EXTERNALLY_MANAGED, True,
            [1, 2, 3],
            {"entitlements": [
                {"entitlement_id": 1, "requires_consent": False},
                {"entitlement_id": 2, "requires_consent": False},
                {"entitlement_id": 3, "requires_consent": False},
            ]},
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
        """
        user_id = self.user.id + 1
        enterprise_customer = factories.EnterpriseCustomerFactory(
            enable_data_sharing_consent=enable_data_sharing_consent,
            enforce_data_sharing_consent=enforce_data_sharing_consent,
        )
        user = factories.UserFactory(id=user_id)
        ecu = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer,
        )
        factories.DataSharingConsentFactory(
            username=user.username,
            enterprise_customer=enterprise_customer,
            granted=learner_consent_state,
        )
        for entitlement in entitlements:
            factories.EnterpriseCustomerEntitlementFactory(
                enterprise_customer=enterprise_customer,
                entitlement_id=entitlement,
            )
        url = reverse('enterprise-learner-entitlements', (ecu.id, ))
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)
        assert sorted(response) == sorted(expected_json)

    @override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME=TEST_USERNAME)
    @mock.patch("enterprise.api.v1.serializers.track_enrollment")
    @ddt.data(
        (
            # A valid request.
            True,
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
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            False,
            201
        ),
        (
            # A valid request to an existing enrollment.
            True,
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
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            True,
            201
        ),
        (
            # A bad request due to an invalid user.
            True,
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
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            False,
            400
        ),
        (
            # A rejected request due to missing model permissions.
            False,
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
            False,
            403
        ),
        (
            # A bad request due to a non-existing EnterpriseCustomerUser.
            True,
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
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            },
            False,
            400
        )
    )
    @ddt.unpack
    def test_post_enterprise_course_enrollment(
            self,
            has_permissions,
            factory,
            request_data,
            enrollment_exists,
            status_code,
            mock_track_enrollment,
    ):
        """
        Make sure service users can post new EnterpriseCourseEnrollments.
        """
        factory_type, factory_data = factory
        if factory_type == factories.EnterpriseCustomerUserFactory:
            factory_data[0]['user_id'] = self.user.pk  # pylint: disable=no-member

        self.create_items(*factory)
        if has_permissions:
            permission = Permission.objects.get(name='Can add enterprise course enrollment')
            self.user.user_permissions.add(permission)

        if enrollment_exists:
            enterprise_customer_user = EnterpriseCustomerUser.objects.get(user_id=self.user.pk)
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=enterprise_customer_user,
                course_id=request_data['course_id'],
            )

        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT,
            data=request_data
        )
        assert response.status_code == status_code
        response = self.load_json(response.content)

        if status_code == 201:
            self.assertDictEqual(request_data, response)
            if enrollment_exists:
                mock_track_enrollment.assert_not_called()
            else:
                mock_track_enrollment.assert_called_once_with(
                    'rest-api-enrollment',
                    self.user.id,
                    request_data['course_id'],
                )
        else:
            mock_track_enrollment.assert_not_called()

    def test_get_enterprise_customer_user_contains_consent_records(self):
        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        factories.DataSharingConsentFactory(
            username=user.username,
            enterprise_customer=enterprise_customer,
            course_id=TEST_COURSE,
            granted=True
        )

        expected_json = [{
            'username': user.username,
            'enterprise_customer_uuid': FAKE_UUIDS[0],
            'exists': True,
            'course_id': TEST_COURSE,
            'consent_provided': True,
            'consent_required': False
        }]

        response = self.client.get(
            '{host}{path}?username={username}'.format(
                host=settings.TEST_SERVER,
                path=ENTERPRISE_LEARNER_LIST_ENDPOINT,
                username=user.username
            )
        )
        response = self.load_json(response.content)
        assert expected_json == response['results'][0]['data_sharing_consent_records']

    def test_get_enterprise_customer_user_with_groups(self):
        user = factories.UserFactory()
        group1 = factories.GroupFactory(name='enterprise_enrollment_api_access')
        group1.user_set.add(user)
        group2 = factories.GroupFactory(name='some_other_group')
        group2.user_set.add(user)
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )

        expected_groups = ['enterprise_enrollment_api_access']

        response = self.client.get(
            '{host}{path}?username={username}'.format(
                host=settings.TEST_SERVER,
                path=ENTERPRISE_LEARNER_LIST_ENDPOINT,
                username=user.username
            )
        )
        response = self.load_json(response.content)
        assert expected_groups == response['results'][0]['groups']

    @override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME=TEST_USERNAME)
    @ddt.data(
        (True, 201),
        (False, 403)
    )
    @ddt.unpack
    def test_post_enterprise_customer_user(self, has_permissions, status_code):
        """
        Make sure service users can post new EnterpriseCustomerUsers.
        """
        factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        data = {
            'enterprise_customer': FAKE_UUIDS[0],
            'username': TEST_USERNAME,
        }
        if has_permissions:
            permission = Permission.objects.get(name='Can add Enterprise Customer Learner')
            self.user.user_permissions.add(permission)

        response = self.client.post(settings.TEST_SERVER + ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == status_code
        response = self.load_json(response.content)

        if status_code == 201:
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
        response = self.client.post(settings.TEST_SERVER + ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == 401

    @ddt.data(
        (
            FAKE_UUIDS[0],
            1,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            False,
            False,
            {},
            {'detail': 'Not found.'}
        ),
        (
            FAKE_UUIDS[0],
            None,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            False,
            True,
            {},
            {'detail': (
                "No catalog is associated with Enterprise Pied Piper from endpoint "
                "'/enterprise/api/v1/enterprise-customer/" + FAKE_UUIDS[0] + "/courses/'."
            )}
        ),
        (
            FAKE_UUIDS[0],
            None,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            True,
            False,
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
            False,
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
            False,
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
        (
            FAKE_UUIDS[0],
            1,
            ENTERPRISE_CUSTOMER_COURSES_ENDPOINT,
            False,
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
            is_staff,
            is_linked_to_enterprise,
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

        self.user.is_staff = is_staff
        self.user.save()
        if is_linked_to_enterprise:
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
            factories.EnterpriseCustomerFactory,
            ENTERPRISE_CUSTOMER_LIST_ENDPOINT,
            itemgetter('uuid'),
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'site__domain': 'example.com', 'site__name': 'example.com',
            }],
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': None, 'enterprise_customer_entitlements': [],
                'enable_audit_enrollment': False, 'identity_provider': None,
                'replace_sensitive_sso_username': False,
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
            }],
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            ENTERPRISE_LEARNER_LIST_ENDPOINT,
            itemgetter('user_id'),
            [{
                'id': 1, 'user_id': 0,
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'enterprise_customer__name': 'Test Enterprise Customer',
                'enterprise_customer__slug': TEST_SLUG, 'enterprise_customer__catalog': 1,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com',
                'enterprise_customer__site__name': 'example.com',

            }],
            [{
                'id': 1, 'user_id': 0, 'user': None, 'data_sharing_consent_records': [], 'groups': [],
                'enterprise_customer': {
                    'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                    'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_enrollment',
                    'branding_configuration': None, 'enterprise_customer_entitlements': [],
                    'enable_audit_enrollment': False, 'identity_provider': None,
                    'replace_sensitive_sso_username': False,
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
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            }],
            [{
                'enterprise_customer_user': 1,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
            }],
        ),
        (
            factories.EnterpriseCustomerIdentityProviderFactory,
            ENTERPRISE_CUSTOMER_LIST_ENDPOINT,
            itemgetter('uuid'),
            [{
                'provider_id': FAKE_UUIDS[0],
                'enterprise_customer__uuid': FAKE_UUIDS[1],
                'enterprise_customer__name': 'Test Enterprise Customer',
                'enterprise_customer__slug': TEST_SLUG, 'enterprise_customer__catalog': 1,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com',
                'enterprise_customer__site__name': 'example.com',

            }],
            [{
                'uuid': FAKE_UUIDS[1], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': None, 'enterprise_customer_entitlements': [],
                'enable_audit_enrollment': False, 'identity_provider': FAKE_UUIDS[0],
                'replace_sensitive_sso_username': False,
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
            }],
        ),
        (
            factories.EnterpriseCustomerBrandingConfigurationFactory,
            ENTERPRISE_CUSTOMER_BRANDING_LIST_ENDPOINT,
            itemgetter('enterprise_customer'),
            [{
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'enterprise_customer__slug': TEST_SLUG,
                'logo': 'enterprise/branding/1/1_logo.png',
            }],
            [{
                'enterprise_customer': FAKE_UUIDS[0],
                'enterprise_slug': TEST_SLUG,
                'logo': 'http://testserver/enterprise/branding/1/1_logo.png',
            }],
        ),
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

    def test_enterprise_customer_reporting_list(self):
        """
        ``enterprise_customer_reporting``'s list endpoint should serialize the ``EnterpriseCustomerReportingConfig``.
        """
        factory = factories.EnterpriseCustomerReportingConfigFactory
        model_item = {
            'enterprise_customer__uuid': FAKE_UUIDS[0],
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
        }
        expected_item = {
            'enterprise_customer': {
                'uuid': FAKE_UUIDS[0],
            },
            'active': True,
            'delivery_method': 'email',
            'frequency': 'monthly',
            'email': ['test@test.com', 'foo@test.com'],
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'report_type': 'csv',
            'data_type': 'progress',
        }
        self.create_items(factory, [model_item])
        response = self.client.get(settings.TEST_SERVER + ENTERPRISE_CUSTOMER_REPORTING_ENDPOINT)
        response = self.load_json(response.content)
        result_item = response['results'][0]
        for key in expected_item:
            if key == 'enterprise_customer':
                assert expected_item[key]['uuid'] == result_item[key]['uuid']
            else:
                assert expected_item[key] == result_item[key]

        assert result_item['encrypted_password'] is not None
        assert result_item['encrypted_sftp_password'] is not None

    @ddt.data(
        # Request missing required permissions query param.
        (True, False, [], {}, False, {'detail': 'User is not allowed to access the view.'}),
        # Staff user that does not have the specified group permission.
        (True, False, [], {'permissions': ['enterprise_enrollment_api_access']}, False,
         {'detail': 'User is not allowed to access the view.'}),
        # Staff user that does have the specified group permission.
        (True, False, ['enterprise_enrollment_api_access'], {'permissions': ['enterprise_enrollment_api_access']},
         True, None),
        # Non staff user that is not linked to the enterprise, nor do they have the group permission.
        (False, False, [], {'permissions': ['enterprise_enrollment_api_access']}, False,
         {'detail': 'User is not allowed to access the view.'}),
        # Non staff user that is not linked to the enterprise, but does have the group permission.
        (False, False, ['enterprise_enrollment_api_access'], {'permissions': ['enterprise_enrollment_api_access']},
         False, {'count': 0, 'next': None, 'previous': None, 'results': []}),
        # Non staff user that is linked to the enterprise, but does not have the group permission.
        (False, True, [], {'permissions': ['enterprise_enrollment_api_access']}, False,
         {'detail': 'User is not allowed to access the view.'}),
        # Non staff user that is linked to the enterprise and does have the group permission
        (False, True, ['enterprise_enrollment_api_access'], {'permissions': ['enterprise_enrollment_api_access']},
         True, None),
        # Non staff user that is linked to the enterprise and has group permission and the request has passed
        # multiple groups to check.
        (False, True, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access', 'enterprise_data_api_access']}, True, None),
        # Staff user with group permission filtering on non existent enteprise id.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'enterprise_id': FAKE_UUIDS[1]}, False,
         {'count': 0, 'next': None, 'previous': None, 'results': []}),
        # Staff user with group permission filtering on enterprise id successfully.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'enterprise_id': FAKE_UUIDS[0]}, True, None),
        # Staff user with group permission filtering on search param with no results.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'search': 'blah'}, False,
         {'count': 0, 'next': None, 'previous': None, 'results': []}),
        # Staff user with group permission filtering on search param with results.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'search': 'test'}, True, None),
        # Staff user with group permission filtering on slug with results.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'slug': TEST_SLUG}, True, None),
        # Staff user with group permissions filtering on slug with no results.
        (True, False, ['enterprise_enrollment_api_access'],
         {'permissions': ['enterprise_enrollment_api_access'], 'slug': 'blah'}, False,
         {'count': 0, 'next': None, 'previous': None, 'results': []}),
    )
    @ddt.unpack
    def test_enterprise_customer_with_access_to(
            self,
            is_staff,
            is_linked_to_enterprise,
            user_groups,
            query_params,
            has_access_to_enterprise,
            expected_error
    ):
        """
        ``enterprise_customer``'s detail list endpoint ``with_access_to`` should validate permissions
         and serialize the ``EnterpriseCustomer`` objects the user has access to.
        """
        enterprise_customer_data = {
            'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
            'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
            'enforce_data_sharing_consent': 'at_enrollment',
            'site__domain': 'example.com', 'site__name': 'example.com',
        }
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_customer_data)

        # creating a non staff user so verify the insufficient permission conditions.
        user = factories.UserFactory(username='test_user', is_active=True, is_staff=is_staff)
        user.set_password('test_password')  # pylint: disable=no-member
        user.save()  # pylint: disable=no-member

        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=enterprise_customer,
            )

        for group_name in user_groups:
            group = factories.GroupFactory(name=group_name)
            group.user_set.add(user)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        response = client.get(settings.TEST_SERVER +
                              ENTERPRISE_CUSTOMER_WITH_ACCESS_TO_ENDPOINT +
                              '?' + urlencode(query_params, True))
        response = self.load_json(response.content)
        if has_access_to_enterprise:
            assert response['results'][0] == {
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'catalog': 1, 'active': True, 'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': None, 'enterprise_customer_entitlements': [],
                'enable_audit_enrollment': False, 'identity_provider': None,
                'replace_sensitive_sso_username': False,
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
            }
        else:
            assert response == expected_error

    def test_enterprise_customer_branding_detail(self):
        """
        ``enterprise_customer_branding``'s get endpoint should get the config by looking up the enterprise slug and
         serialize the ``EnterpriseCustomerBrandingConfig``.
        """
        factory = factories.EnterpriseCustomerBrandingConfigurationFactory
        model_items = [
            {
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'enterprise_customer__slug': TEST_SLUG,
                'logo': 'enterprise/branding/1/1_logo.png',
            },
            {
                'enterprise_customer__uuid': FAKE_UUIDS[1],
                'enterprise_customer__slug': 'another-slug',
                'logo': 'enterprise/branding/2/2_logo.png',
            },
        ]
        expected_item = {
            'enterprise_customer': FAKE_UUIDS[0],
            'enterprise_slug': TEST_SLUG,
            'logo': 'http://testserver/enterprise/branding/1/1_logo.png',
        }
        self.create_items(factory, model_items)
        response = self.client.get(settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BRANDING_DETAIL_ENDPOINT)
        response = self.load_json(response.content)
        assert expected_item == response

    @ddt.data(
        (False, False),
        (False, True),
        (True, False),
    )
    @ddt.unpack
    def test_enterprise_customer_catalogs_list(self, is_staff, is_linked_to_enterprise):
        """
        ``enterprise_catalogs``'s list endpoint should serialize the ``EnterpriseCustomerCatalog`` model.
        """
        catalog_uuid = FAKE_UUIDS[1]
        catalog_title = 'All Content'
        catalog_filter = {}
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0]
        )
        factories.EnterpriseCustomerCatalogFactory(
            uuid=catalog_uuid,
            title=catalog_title,
            enterprise_customer=enterprise_customer,
            content_filter=catalog_filter
        )
        self.user.is_staff = is_staff
        self.user.save()
        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer,
            )
        if is_staff or is_linked_to_enterprise:
            expected_results = {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'uuid': catalog_uuid,
                    'title': catalog_title,
                    'enterprise_customer': enterprise_customer.uuid
                }]
            }
        else:
            expected_results = {
                'count': 0,
                'next': None,
                'previous': None,
                'results': []
            }

        response = self.client.get(ENTERPRISE_CATALOGS_LIST_ENDPOINT)
        response = self.load_json(response.content)

        assert response == expected_results

    @ddt.data(
        (
            False,
            False,
            {'detail': 'Not found.'},
        ),
        (
            False,
            True,
            fake_enterprise_api.build_fake_enterprise_catalog_detail(
                paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                include_enterprise_context=True,
                add_utm_info=False
            ),
        ),
        (
            True,
            False,
            fake_enterprise_api.build_fake_enterprise_catalog_detail(
                paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                include_enterprise_context=True,
                add_utm_info=False
            ),
        ),
        (
            True,
            True,
            fake_enterprise_api.build_fake_enterprise_catalog_detail(
                paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                include_enterprise_context=True,
                add_utm_info=False
            ),
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch("enterprise.utils.update_query_parameters", mock.MagicMock(side_effect=side_effect))
    def test_enterprise_customer_catalogs_detail(
            self,
            is_staff,
            is_linked_to_enterprise,
            expected_result,
            mock_catalog_api_client,
    ):
        """
        Make sure the Enterprise Customer's Catalog view correctly returns details about specific catalogs based on
        the content filter.

        Search results should also take into account whether

        * requesting user is staff.
        * requesting user is linked to the EnterpriseCustomer which owns the requested catalog.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer
        )
        if not is_staff:
            self.user.is_staff = False
            self.user.save()
        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(
                return_value=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS
            ),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_DETAIL_ENDPOINT)
        response = self.load_json(response.content)

        self.assertDictEqual(response, expected_result)

    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch("enterprise.utils.update_query_parameters", mock.MagicMock(side_effect=side_effect))
    def test_enterprise_customer_catalogs_detail_pagination(self, mock_catalog_api_client):
        """
        Verify the EnterpriseCustomerCatalog detail view returns the correct paging URLs.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(
                return_value=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS_WITH_PAGINATION
            ),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_DETAIL_ENDPOINT + '?page=2')
        response = self.load_json(response.content)

        expected_result = fake_enterprise_api.build_fake_enterprise_catalog_detail(
            paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS_2,
            previous_url=urljoin('http://testserver', ENTERPRISE_CATALOGS_DETAIL_ENDPOINT) + '?page=1',
            next_url=urljoin('http://testserver/', ENTERPRISE_CATALOGS_DETAIL_ENDPOINT) + '?page=3',
            include_enterprise_context=True, add_utm_info=False
        )

        assert response == expected_result

    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch("enterprise.utils.update_query_parameters", mock.MagicMock(side_effect=side_effect))
    def test_enterprise_customer_catalogs_detail_pagination_filtering(self, mock_catalog_api_client):
        """
        Verify the EnterpriseCustomerCatalog detail view returns the correct paging URLs.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(
                return_value=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS_WITH_PAGINATION_1
            ),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_DETAIL_ENDPOINT + '?page=2')
        response = self.load_json(response.content)

        expected_result = fake_enterprise_api.build_fake_enterprise_catalog_detail(
            paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS_3,
            previous_url=urljoin('http://testserver', ENTERPRISE_CATALOGS_DETAIL_ENDPOINT) + '?page=1',
            next_url=urljoin('http://testserver/', ENTERPRISE_CATALOGS_DETAIL_ENDPOINT) + '?page=3', add_utm_info=False)

        assert response == expected_result

    @ddt.data(
        (False, {'course_run_ids': ['fake1', 'fake2']}, None),
        (False, {'program_uuids': ['fake1', 'fake2']}, None),
        (
            True,
            {
                'course_run_ids': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ]
            },
            [fake_catalog_api.FAKE_COURSE_RUN, fake_catalog_api.FAKE_COURSE_RUN2]
        ),
        (
            True,
            {
                'program_uuids': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            },
            [fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1, fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2]
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_contains_content_items_with_search(self, contains_content_items, query_params,
                                                                   search_results, mock_catalog_api_client):
        """
        Ensure contains_content_items endpoint returns expected result when
        the discovery service's search endpoint is used to determine whether
        or not the catalog contains the given content items.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=search_results)
        )

        response = self.client.get(ENTERPRISE_CATALOGS_CONTAINS_CONTENT_ENDPOINT + '?' + urlencode(query_params, True))
        response_json = self.load_json(response.content)

        assert response_json['contains_content_items'] == contains_content_items

    @ddt.data(
        (False, {'course_run_ids': ['fake1', 'fake2']}),
        (False, {'program_uuids': ['fake1', 'fake2']}),
        (
            True,
            {
                'course_run_ids': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ]
            },
        ),
        (
            True,
            {
                'program_uuids': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            },
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_contains_content_items_without_search(self, contains_content_items, query_params,
                                                                      mock_catalog_api_client):
        """
        Ensure contains_content_items endpoint returns expected result when
        the catalog's content_filter specifies unique keys.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
            content_filter={
                'key': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ],
                'uuid': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            }
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=None)
        )

        response = self.client.get(ENTERPRISE_CATALOGS_CONTAINS_CONTENT_ENDPOINT + '?' + urlencode(query_params, True))
        response_json = self.load_json(response.content)

        assert response_json['contains_content_items'] == contains_content_items

    def test_enterprise_catalog_contains_content_items_no_query_params(self):
        """
        Ensure contains_content_items endpoint returns error message
        when no query parameters are provided.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
        )

        response = self.client.get(ENTERPRISE_CATALOGS_CONTAINS_CONTENT_ENDPOINT)
        response_json = self.load_json(response.content)

        message = response_json[0]
        assert 'program_uuids' in message
        assert 'course_run_ids' in message
        assert response.status_code == 400

    @ddt.data(
        (False, False, False, {}, {'detail': 'Not found.'}),
        (False, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (False, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            False,
            True,
            True,
            fake_catalog_api.FAKE_COURSE_RUN,
            update_course_run_with_enterprise_context(
                fake_catalog_api.FAKE_COURSE_RUN,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
        (True, False, False, {}, {'detail': 'Not found.'}),
        (True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            True,
            True,
            True,
            fake_catalog_api.FAKE_COURSE_RUN,
            update_course_run_with_enterprise_context(
                fake_catalog_api.FAKE_COURSE_RUN,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_course_run_detail(self, is_staff, is_linked_to_enterprise, is_course_run_in_catalog,
                                                  mocked_course_run, expected_result, mock_catalog_api_client):
        """
        The ``course_run`` detail endpoint should return correct results from course discovery,
        with enterprise context in courses.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0], name="test_enterprise")
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
        )
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
        search_results = None
        if is_course_run_in_catalog:
            search_results = [fake_catalog_api.FAKE_COURSE_RUN]

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=search_results),
            get_course_run=mock.Mock(return_value=mocked_course_run),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_COURSE_RUN_ENDPOINT)
        response = self.load_json(response.content)

        assert response == expected_result

    @ddt.data(
        (False, False, False, {}, {'detail': 'Not found.'}),
        (False, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (False, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            False,
            True,
            True,
            fake_catalog_api.FAKE_COURSE,
            update_course_with_enterprise_context(
                fake_catalog_api.FAKE_COURSE,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
        (True, False, False, {}, {'detail': 'Not found.'}),
        (True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            True,
            True,
            True,
            fake_catalog_api.FAKE_COURSE,
            update_course_with_enterprise_context(
                fake_catalog_api.FAKE_COURSE,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_course_detail(self, is_staff, is_linked_to_enterprise, is_course_in_catalog,
                                              mocked_course, expected_result, mock_catalog_api_client):
        """
        The ``course`` detail endpoint should return correct results from course discovery,
        with enterprise context in courses and course runs.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0], name="test_enterprise")
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
        )
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
        search_results = None
        if is_course_in_catalog:
            search_results = [fake_catalog_api.FAKE_COURSE]

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=search_results),
            get_course_details=mock.Mock(return_value=mocked_course),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_COURSE_ENDPOINT)
        response = self.load_json(response.content)

        assert response == expected_result

    @ddt.data(
        (False, False, False, False, {}, {'detail': 'Not found.'}),
        (False, True, False, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (False, True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            False,
            True,
            True,
            True,
            fake_catalog_api.FAKE_PROGRAM_RESPONSE1,
            update_program_with_enterprise_context(
                fake_catalog_api.FAKE_PROGRAM_RESPONSE1,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
        (True, False, False, False, {}, {'detail': 'Not found.'}),
        (True, True, False, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (True, True, True, False, {'detail': 'Not found.'}, {'detail': 'Not found.'}),
        (
            True,
            True,
            True,
            True,
            fake_catalog_api.FAKE_PROGRAM_RESPONSE1,
            update_program_with_enterprise_context(
                fake_catalog_api.FAKE_PROGRAM_RESPONSE1,
                add_utm_info=True,
                enterprise_catalog_uuid=FAKE_UUIDS[1]
            ),
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_program_detail(self, is_staff, is_linked_to_enterprise, has_existing_catalog,
                                               is_program_in_catalog, mocked_program, expected_result,
                                               mock_catalog_api_client):
        """
        The ``programs`` detail endpoint should return correct results from course discovery,
        with enterprise context in courses and course runs.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0], name="test_enterprise")
        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=enterprise_customer,
            provider_id='saml-testshib',
        )
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )
        if has_existing_catalog:
            factories.EnterpriseCustomerCatalogFactory(
                uuid=FAKE_UUIDS[1],
                enterprise_customer=enterprise_customer,
            )
        search_results = None
        if is_program_in_catalog:
            search_results = [fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1]

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=search_results),
            get_program_by_uuid=mock.Mock(return_value=mocked_program),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_PROGRAM_ENDPOINT)
        response = self.load_json(response.content)

        assert response == expected_result

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

    @ddt.data(
        (False, {'course_run_ids': ['fake1', 'fake2']}, None),
        (False, {'program_uuids': ['fake1', 'fake2']}, None),
        (
            True,
            {
                'course_run_ids': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ]
            },
            [fake_catalog_api.FAKE_COURSE_RUN, fake_catalog_api.FAKE_COURSE_RUN2]
        ),
        (
            True,
            {
                'program_uuids': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            },
            [fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1, fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2]
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    def test_enterprise_customer_contains_content_items(self, contains_content_items, query_params, search_results,
                                                        mock_catalog_api_client):
        """
        Ensure contains_content_items endpoint returns expected result when query parameters are provided.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_search_results=mock.Mock(return_value=search_results)
        )

        response = self.client.get(ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT + '?' + urlencode(query_params, True))
        response_json = self.load_json(response.content)

        assert response_json['contains_content_items'] == contains_content_items

    def test_enterprise_customer_contains_content_items_no_catalogs(self):
        """
        Ensure contains_content_items endpoint returns False when the EnterpriseCustomer
        does not have any associated EnterpriseCustomerCatalogs.
        """
        factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        query_params = {'course_run_ids': [
            fake_catalog_api.FAKE_COURSE_RUN['key'],
            fake_catalog_api.FAKE_COURSE_RUN2['key']
        ]}

        response = self.client.get(ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT + '?' + urlencode(query_params, True))
        response_json = self.load_json(response.content)

        assert response_json['contains_content_items'] is False

    def test_enterprise_customer_contains_content_items_no_query_params(self):
        """
        Ensure contains_content_items endpoint returns an error when no query parameters are provided.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerCatalogFactory(
            uuid=FAKE_UUIDS[1],
            enterprise_customer=enterprise_customer,
        )

        response = self.client.get(ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT)
        response_json = self.load_json(response.content)

        message = response_json[0]
        assert 'program_uuids' in message
        assert 'course_run_ids' in message
        assert response.status_code == 400

    def test_enterprise_customer_course_enrollments_no_permissions(self):
        """
        Test the Enterprise Customer course enrollments detail route with insufficient permissions.
        """
        factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        # creating a non staff user so verify the insufficient permission conditions.
        user = factories.UserFactory(username='test_user', is_active=True, is_staff=False)
        user.set_password('test_password')  # pylint: disable=no-member
        user.save()  # pylint: disable=no-member
        client = APIClient()
        client.login(username='test_user', password='test_password')
        expected_result = {u'detail': u'User is not allowed to access the view.'}

        # Make the call!
        response = client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT,
            data=json.dumps([{}]),
            content_type='application/json',
        )
        response = self.load_json(response.content)

        self.assertDictEqual(response, expected_result)

    def test_enterprise_customer_course_enrollments_non_list_request(self):
        """
        Test the Enterprise Customer course enrollments detail route with an invalid expected json format.
        """
        factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)

        expected_result = {'non_field_errors': ['Expected a list of items but got type "dict".']}

        # Make the call!
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT,
            data=json.dumps({}),
            content_type='application/json',
        )
        response = self.load_json(response.content)

        self.assertDictEqual(response, expected_result)

    def create_course_enrollments_context(
            self,
            user_exists,
            lms_user_id,
            tpa_user_id,
            user_email,
            mock_tpa_client,
            mock_enrollment_client,
            course_enrollment,
            mock_catalog_contains_course,
            course_in_catalog,
    ):
        """
        Set up for tests that call the enterprise customer course enrollments detail route.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)

        user = None
        # Create a preexisting EnterpriseCustomerUser
        if user_exists:
            if lms_user_id:
                user = factories.UserFactory(id=lms_user_id)
            elif tpa_user_id:
                user = factories.UserFactory(username=tpa_user_id)
            elif user_email:
                user = factories.UserFactory(email=user_email)

            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=enterprise_customer,
            )

        # Set up ThirdPartyAuth API response
        if tpa_user_id:
            mock_tpa_client.return_value = mock.Mock()
            mock_tpa_client.return_value.get_username_from_remote_id = mock.Mock()
            mock_tpa_client.return_value.get_username_from_remote_id.return_value = tpa_user_id

        # Set up EnrollmentAPI responses
        mock_enrollment_client.return_value = mock.Mock(
            get_course_enrollment=mock.Mock(return_value=course_enrollment),
            enroll_user_in_course=mock.Mock()
        )

        # Set up catalog_contains_course response.
        mock_catalog_contains_course.return_value = course_in_catalog

        return enterprise_customer, user

    @ddt.data(
        (
            False,
            False,
            None,
            [{}],
            [{'course_mode': ['This field is required.'], 'course_run_id': ['This field is required.']}],
        ),
        (
            False,
            True,
            None,
            [{'course_mode': 'audit', 'course_run_id': 'course-v1:edX+DemoX+Demo_Course'}],
            [{
                'non_field_errors': [
                    'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                    'lms_user_id, tpa_user_id, user_email'
                ]
            }],
        ),
        (
            False,
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
            }],
            [{
                'non_field_errors': [
                    'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                    'lms_user_id, tpa_user_id, user_email'
                ]
            }],
        ),
        (
            False,
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'tpa_user_id': 'abc',
            }],
            [{
                'non_field_errors': [
                    'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                    'lms_user_id, tpa_user_id, user_email'
                ]
            }],
        ),
        (
            True,
            False,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
            }],
            [{
                'course_run_id': [
                    'The course run id course-v1:edX+DemoX+Demo_Course is not in the catalog '
                    'for Enterprise Customer test_enterprise'
                ]
            }],
        ),
        (
            False,
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
                'tpa_user_id': 'abc',
            }],
            [{
                'non_field_errors': [
                    'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                    'lms_user_id, tpa_user_id, user_email'
                ]
            }],
        ),
        (
            True,
            True,
            {'is_active': True, 'mode': 'verified'},
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
            }],
            [{
                'detail': (
                    'The user is already enrolled in the course course-v1:edX+DemoX+Demo_Course '
                    'in verified mode and cannot be enrolled in audit mode'
                )
            }],
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    @mock.patch('enterprise.api.v1.serializers.ThirdPartyAuthApiClient')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.utils.track_event', mock.MagicMock())
    def test_enterprise_customer_course_enrollments_detail_errors(
            self,
            user_exists,
            course_in_catalog,
            course_enrollment,
            post_data,
            expected_result,
            mock_enrollment_client,
            mock_tpa_client,
            mock_catalog_contains_course,
    ):
        """
        Test the Enterprise Customer course enrollments detail route error cases.
        """
        payload = post_data[0]
        self.create_course_enrollments_context(
            user_exists,
            payload.get('lms_user_id'),
            payload.get('tpa_user_id'),
            payload.get('user_email'),
            mock_tpa_client,
            mock_enrollment_client,
            course_enrollment,
            mock_catalog_contains_course,
            course_in_catalog
        )

        # Make the call!
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT,
            data=json.dumps(post_data),
            content_type='application/json',
        )
        response = self.load_json(response.content)

        self.assertListEqual(response, expected_result)

    @ddt.data(
        (
            False,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
                'tpa_user_id': 'abc',
                'user_email': 'abc@test.com',
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'tpa_user_id': 'abc',
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'user_email': 'abc@test.com',
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
                'email_students': True
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
                'email_students': True,
                'cohort': 'masters',
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'user_email': 'foo@bar.com',
                'email_students': True,
                'cohort': 'masters',
            }],
        ),
        (
            True,
            {'is_active': True, 'mode': 'audit'},
            [{
                'course_mode': 'verified',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
            }],
        ),
        (
            True,
            {'is_active': False, 'mode': 'audit'},
            [{
                'course_mode': 'verified',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 1,
                'is_active': False,
            }],
        ),
        (
            False,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'user_email': 'foo@bar.com',
                'is_active': False,
            }],
        ),

    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    @mock.patch('enterprise.api.v1.serializers.ThirdPartyAuthApiClient')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCustomer.notify_enrolled_learners')
    @mock.patch('enterprise.models.utils.track_event', mock.MagicMock())
    def test_enterprise_customer_course_enrollments_detail_success(
            self,
            user_exists,
            course_enrollment,
            post_data,
            mock_notify_learners,
            mock_enrollment_client,
            mock_tpa_client,
            mock_catalog_contains_course,
    ):
        """
        Test the Enterprise Customer course enrollments detail route in successful cases.
        """
        payload = post_data[0]
        enterprise_customer, user = self.create_course_enrollments_context(
            user_exists,
            payload.get('lms_user_id'),
            payload.get('tpa_user_id'),
            payload.get('user_email'),
            mock_tpa_client,
            mock_enrollment_client,
            course_enrollment,
            mock_catalog_contains_course,
            True
        )

        # Make the call!
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT,
            data=json.dumps(post_data),
            content_type='application/json',
        )
        response = self.load_json(response.content)

        expected_response = [{'detail': 'success'}]
        self.assertListEqual(response, expected_response)

        if user_exists:
            if course_enrollment and not course_enrollment['is_active']:
                # check that the user was unenrolled
                assert not EnterpriseCourseEnrollment.objects.filter(
                    enterprise_customer_user__user_id=user.id,
                    course_id=payload.get('course_run_id'),
                ).exists()
                mock_enrollment_client.return_value.unenroll_user_from_course.assert_called_once_with(
                    user.username,
                    payload.get('course_run_id')
                )
            else:
                # If the user already existed, check that the enrollment was performed.
                assert EnterpriseCourseEnrollment.objects.filter(
                    enterprise_customer_user__user_id=user.id,
                    course_id=payload.get('course_run_id'),
                ).exists()
                mock_enrollment_client.return_value.get_course_enrollment.assert_called_once_with(
                    user.username, payload.get('course_run_id')
                )
                mock_enrollment_client.return_value.enroll_user_in_course.assert_called_once_with(
                    user.username,
                    payload.get('course_run_id'),
                    payload.get('course_mode'),
                    cohort=payload.get('cohort'),
                )
        elif 'user_email' in post_data:
            # If a new user given via for user_email, check that the appropriate objects were created.
            pending_ecu = PendingEnterpriseCustomerUser.objects.get(
                enterprise_customer=enterprise_customer,
                user_email=payload.get('user_email')
            )

            assert pending_ecu is not None
            pending_enrollment = PendingEnrollment.objects.filter(
                user=pending_ecu,
                course_id=payload.get('course_run_id'),
                course_mode=payload.get('course_mode')
            )
            if payload.get('is_active', True):
                assert pending_enrollment
                assert pending_enrollment.cohort_name == payload.get('cohort')
            else:
                assert not pending_enrollment
            mock_enrollment_client.return_value.get_course_enrollment.assert_not_called()
            mock_enrollment_client.return_value.enroll_user_in_course.assert_not_called()

        if 'email_students' in payload:
            mock_notify_learners.assert_called_once()
        else:
            mock_notify_learners.assert_not_called()

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    @mock.patch('enterprise.api.v1.serializers.ThirdPartyAuthApiClient')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.utils.track_event', mock.MagicMock())
    def test_enterprise_customer_course_enrollments_detail_multiple(
            self,
            mock_enrollment_client,
            mock_tpa_client,
            mock_catalog_contains_course,
    ):
        """
        Test the Enterprise Customer course enrollments detail route with multiple enrollments sent.
        """
        tpa_user_id = 'abc'
        new_user_email = 'abc@test.com'
        pending_email = 'foo@bar.com'
        lms_user_id = 1
        course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        payload = [
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'tpa_user_id': tpa_user_id,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'user_email': new_user_email,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'lms_user_id': lms_user_id,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'user_email': pending_email,
                'cohort': 'test'
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'user_email': pending_email,
                'is_active': False,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'user_email': pending_email,
                'is_active': True,
            },
            {
                'course_mode': 'audit',
                'course_run_id': course_run_id,
                'user_email': pending_email,
                'is_active': False,
            }
        ]

        expected_response = [
            {'detail': 'success'},
            {'detail': 'success'},
            {
                'detail': (
                    'The user is already enrolled in the course course-v1:edX+DemoX+Demo_Course '
                    'in verified mode and cannot be enrolled in audit mode'
                )
            },
            {
                'non_field_errors': [
                    'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                    'lms_user_id, tpa_user_id, user_email'
                ]
            },
            {'detail': 'success'},
            {'detail': 'success'},
            {'detail': 'success'},
            {'detail': 'success'},
        ]

        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)

        # Create a preexisting EnterpriseCustomerUsers
        tpa_user = factories.UserFactory(username=tpa_user_id)
        lms_user = factories.UserFactory(id=lms_user_id)

        factories.EnterpriseCustomerUserFactory(
            user_id=tpa_user.id,
            enterprise_customer=enterprise_customer,
        )

        factories.EnterpriseCustomerUserFactory(
            user_id=lms_user.id,
            enterprise_customer=enterprise_customer,
        )

        # Set up ThirdPartyAuth API response
        mock_tpa_client.return_value = mock.Mock()
        mock_tpa_client.return_value.get_username_from_remote_id = mock.Mock()
        mock_tpa_client.return_value.get_username_from_remote_id.return_value = tpa_user_id

        # Set up EnrollmentAPI responses
        mock_enrollment_client.return_value = mock.Mock(
            get_course_enrollment=mock.Mock(
                side_effect=[None, {'is_active': True, 'mode': 'verified'}]
            ),
            enroll_user_in_course=mock.Mock()
        )

        # Set up catalog_contains_course response.
        mock_catalog_contains_course.return_value = True

        # Make the call!
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT,
            data=json.dumps(payload),
            content_type='application/json',
        )
        response = self.load_json(response.content)

        self.assertListEqual(response, expected_response)
        self.assertFalse(PendingEnrollment.objects.filter(
            user__user_email=pending_email,
            course_id=course_run_id).exists())

    def test_enterprise_customer_catalogs_response_formats(self):
        """
        ``enterprise_catalogs``'s xml and json responses verification.
        """
        response_default = self.client.get('/enterprise/api/v1/enterprise_catalogs/')
        self.assertTrue(response_default['content-type'] == 'application/json')

        response_json = self.client.get('/enterprise/api/v1/enterprise_catalogs.json')
        self.assertTrue(response_json['content-type'] == 'application/json')

        response_xml = self.client.get('/enterprise/api/v1/enterprise_catalogs.xml')
        self.assertTrue(response_xml['content-type'] == 'application/xml; charset=utf-8')
