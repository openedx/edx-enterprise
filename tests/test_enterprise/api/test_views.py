"""
Tests for the `edx-enterprise` api module.
"""

import copy
import json
import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from operator import itemgetter
from smtplib import SMTPException
from unittest import mock
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import ddt
from faker import Faker
from pytest import mark, raises
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testfixtures import LogCapture

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from enterprise.api.v1 import serializers
from enterprise.api.v1.views.enterprise_subsidy_fulfillment import LicensedEnterpriseCourseEnrollmentViewSet
from enterprise.constants import (
    ALL_ACCESS_CONTEXT,
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
    PATHWAY_CUSTOMER_ADMIN_ENROLLMENT,
)
from enterprise.models import (
    ChatGPTResponse,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerInviteKey,
    EnterpriseCustomerUser,
    EnterpriseEnrollmentSource,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    LearnerCreditEnterpriseCourseEnrollment,
    LicensedEnterpriseCourseEnrollment,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from enterprise.utils import NotConnectedToOpenEdX, localized_utcnow
from enterprise_learner_portal.utils import CourseRunProgressStatuses
from test_utils import (
    FAKE_UUIDS,
    TEST_COURSE,
    TEST_COURSE_KEY,
    TEST_PASSWORD,
    TEST_SLUG,
    TEST_USERNAME,
    APITest,
    enterprise_report_choices,
    factories,
    fake_catalog_api,
    fake_enterprise_api,
    update_course_run_with_enterprise_context,
    update_course_with_enterprise_context,
    update_program_with_enterprise_context,
)
from test_utils.factories import (
    FAKER,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_enterprise_api import get_default_branding_object

fake = Faker()

MOCK_ENTERPRISE_CUSTOMER_MODIFIED = str(datetime.now())
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
    'enterprise-catalogs-course-detail',
    kwargs={'pk': FAKE_UUIDS[1], 'course_key': TEST_COURSE_KEY}
)
ENTERPRISE_CATALOGS_COURSE_RUN_ENDPOINT = reverse(
    'enterprise-catalogs-course-run-detail',
    kwargs={'pk': FAKE_UUIDS[1], 'course_id': TEST_COURSE}
)
ENTERPRISE_CATALOGS_PROGRAM_ENDPOINT = reverse(
    'enterprise-catalogs-program-detail', kwargs={'pk': FAKE_UUIDS[1], 'program_uuid': FAKE_UUIDS[3]}
)
ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT = reverse('enterprise_customer_catalog-list')
ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT = reverse('enterprise-course-enrollment-list')
ENTERPRISE_CUSTOMER_BRANDING_LIST_ENDPOINT = reverse('enterprise-customer-branding-list')
ENTERPRISE_CUSTOMER_BRANDING_DETAIL_ENDPOINT = reverse('enterprise-customer-branding-detail', (TEST_SLUG,))
ENTERPRISE_CUSTOMER_LIST_ENDPOINT = reverse('enterprise-customer-list')
ENTERPRISE_CUSTOMER_DETAIL_ENDPOINT = reverse(
    'enterprise-customer-detail',
    kwargs={'pk': FAKE_UUIDS[0]}
)
ENTERPRISE_CUSTOMER_BASIC_LIST_ENDPOINT = reverse('enterprise-customer-basic-list')
ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT = reverse(
    'enterprise-customer-contains-content-items',
    kwargs={'pk': FAKE_UUIDS[0]}
)
ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT = reverse('enterprise-customer-course-enrollments', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT = reverse(
    'enterprise-customer-enroll-learners-in-courses',
    (FAKE_UUIDS[0],)
)
ENTERPRISE_CUSTOMER_REPORTING_ENDPOINT = reverse('enterprise-customer-reporting-list')
ENTERPRISE_LEARNER_LIST_ENDPOINT = reverse('enterprise-learner-list')
ENTERPRISE_CUSTOMER_WITH_ACCESS_TO_ENDPOINT = reverse('enterprise-customer-with-access-to')
ENTERPRISE_CUSTOMER_UNLINK_USERS_ENDPOINT = reverse('enterprise-customer-unlink-users', kwargs={'pk': FAKE_UUIDS[0]})
PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT = reverse('pending-enterprise-learner-list')
LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT = reverse(
    'licensed-enterprise-course-enrollment-license-revoke'
)
EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT = reverse(
    'licensed-enterprise-course-enrollment-bulk-licensed-enrollments-expiration'
)
VERIFIED_SUBSCRIPTION_COURSE_MODE = 'verified'


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


class BaseTestEnterpriseAPIViews(APITest):
    """
    Shared setup and methods for enterprise api views.
    """
    # Get current datetime, so that all tests can use same datetime.
    now = timezone.now()
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.set_jwt_cookie(ENTERPRISE_OPERATOR_ROLE, ALL_ACCESS_CONTEXT)

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, is_staff=True, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=is_staff, **kwargs)
        self.user.set_password(password)
        self.user.save()

    def create_items(self, factory, items):
        """
        Create model instances using given factory
        """
        for item in items:
            factory.create(**item)

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
            enable_autocohorting=False
    ):
        """
        Set up for tests that call the enterprise customer course enrollments detail route.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise",
            enable_autocohorting=enable_autocohorting
        )
        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=enterprise_customer
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

    def _revocation_factory_objects(self):
        """
        Helper method to provide some testing objects for revocation tests.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory()

        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer,
        )
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
        )
        licensed_course_enrollment = factories.LicensedEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=enterprise_course_enrollment,
        )

        assert not enterprise_course_enrollment.saved_for_later
        assert not licensed_course_enrollment.is_revoked

        return enterprise_customer_user, enterprise_course_enrollment, licensed_course_enrollment


@ddt.ddt
@mark.django_db
class TestCourseEnrollmentView(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCourseEnrollmentViewSet
    """

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
                    'enterprise_customer__name': 'Test Enterprise Customer',
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
                    'enterprise_customer__name': 'Test Enterprise Customer',
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
                    'enterprise_customer__name': 'Test Enterprise Customer',
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
                    'enterprise_customer__name': 'Test Enterprise Customer',
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
                    'active': True, 'enable_data_sharing_consent': True,
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
            factory_data[0]['user_id'] = self.user.pk

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
            enterprise_customer_user = EnterpriseCustomerUser.objects.get(user_id=self.user.pk)
            enrollment = EnterpriseCourseEnrollment.objects.get(
                enterprise_customer_user=enterprise_customer_user,
                course_id=request_data['course_id'],
            )

            self.assertDictEqual(request_data, response)
            if enrollment_exists:
                mock_track_enrollment.assert_not_called()
                assert enrollment.source is None
            else:
                mock_track_enrollment.assert_called_once_with(
                    'rest-api-enrollment',
                    self.user.id,
                    request_data['course_id'],
                )
                assert enrollment.source.slug == EnterpriseEnrollmentSource.OFFER_REDEMPTION
        else:
            mock_track_enrollment.assert_not_called()


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerUser(BaseTestEnterpriseAPIViews):
    """
    Test enteprise learner list endpoint
    """

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
            data.update({'active': True})
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
                'active': True, 'enable_data_sharing_consent': True,
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


@ddt.ddt
@mark.django_db
class TestPendingEnterpriseCustomerUser(BaseTestEnterpriseAPIViews):
    """
    Test PendingEnterpriseCustomerUserViewSet
    """

    def create_ent_user(self, user_exists, ecu_exists, pending_ecu_exists, user_email, enterprise_customer):
        """
        Creates enterprise users or pending users
        """
        user = None
        if user_exists:
            user = factories.UserFactory(email=user_email)
            if ecu_exists:
                factories.EnterpriseCustomerUserFactory(user_id=user.id, enterprise_customer=enterprise_customer)

        if pending_ecu_exists:
            factories.PendingEnterpriseCustomerUserFactory(
                user_email=user_email, enterprise_customer=enterprise_customer
            )
        return user

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    @ddt.data(
        {'is_staff': True, 'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True, 'status_code': 201},
        {'is_staff': True, 'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False, 'status_code': 201},
        {'is_staff': True, 'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False, 'status_code': 201},
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_user_creation(
            self,
            is_staff,
            user_exists,
            ecu_exists,
            pending_ecu_exists,
            status_code):
        """
        Make sure service users can post new PendingEnterpriseCustomerUsers.
        """

        # create user making the request
        self.setup_admin_user(is_staff)

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        user = self.create_ent_user(
            user_exists=user_exists,
            ecu_exists=ecu_exists,
            pending_ecu_exists=pending_ecu_exists,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(settings.TEST_SERVER + PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == status_code
        response = self.load_json(response.content)
        self.assertDictEqual(data, response)
        if not user_exists:
            assert PendingEnterpriseCustomerUser.objects.get(
                user_email=new_user_email, enterprise_customer=enterprise_customer
            )
        else:
            assert EnterpriseCustomerUser.objects.get(
                user_id=user.id, enterprise_customer=enterprise_customer, active=user.is_active
            )

    @ddt.data(
        {'is_staff': True, 'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False, 'status_code': 204},
        {'is_staff': True, 'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True, 'status_code': 204},
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_user_creation_no_user_created(
        self,
        is_staff,
        user_exists,
        ecu_exists,
        pending_ecu_exists,
        status_code
    ):
        """
        Make sure service users can post new PendingEnterpriseCustomerUsers.
        """

        # create user making the request
        self.setup_admin_user(is_staff)

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        self.create_ent_user(
            user_exists=user_exists,
            ecu_exists=ecu_exists,
            pending_ecu_exists=pending_ecu_exists,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(settings.TEST_SERVER + PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == status_code
        assert not response.content

    @ddt.data(
        {'is_staff': False, 'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False, 'status_code': 403},
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_unauthorized_user(
        self,
        is_staff,
        user_exists,
        ecu_exists,
        pending_ecu_exists,
        status_code
    ):
        # create user making the request
        self.setup_admin_user(is_staff)

        # create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        self.create_ent_user(
            user_exists=user_exists,
            ecu_exists=ecu_exists,
            pending_ecu_exists=pending_ecu_exists,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(settings.TEST_SERVER + PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == status_code

    @ddt.data(
        ([{'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True}], 201),
        ([{'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False}], 201),
        ([{'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True}], 204)
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_multiple_customers(self, userlist, status_code):
        self.setup_admin_user()
        ent_uuid = fake.uuid4()

        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        data = []
        users = []
        for idx, user in enumerate(userlist):
            user_email = 'new_user{}@example.com'.format(idx)
            data.append({
                'enterprise_customer': ent_uuid,
                'user_email': user_email
            })

            existing_user = self.create_ent_user(
                user_exists=user['user_exists'],
                ecu_exists=user['ecu_exists'],
                pending_ecu_exists=user['pending_ecu_exists'],
                user_email=user_email,
                enterprise_customer=enterprise_customer,
            )
            users.append({
                'user_exists': user['user_exists'],
                'user_email': user_email,
                'existing_user': existing_user
            })

        response = self.client.post(
            settings.TEST_SERVER + PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT,
            data=data,
            format='json'
        )
        assert response.status_code == status_code
        for user in users:
            # assert that the correct users were created
            if not user['user_exists']:

                assert PendingEnterpriseCustomerUser.objects.get(
                    user_email=user['user_email'], enterprise_customer=enterprise_customer
                )
            else:
                assert EnterpriseCustomerUser.objects.get(
                    user_id=user['existing_user'].id,
                    enterprise_customer=enterprise_customer,
                    active=user['existing_user'].is_active
                )

    def test_post_pending_enterprise_customer_user_logged_out(self):
        """
        Make sure users can't post PendingEnterpriseCustomerUsers when logged out.
        """
        self.client.logout()
        data = {
            'enterprise_customer': FAKE_UUIDS[0],
            'username': self.user.username
        }
        response = self.client.post(settings.TEST_SERVER + PENDING_ENTERPRISE_LEARNER_LIST_ENDPOINT, data=data)
        assert response.status_code == 401


@ddt.ddt
@mark.django_db
class TestPendingEnterpriseCustomerUserEnterpriseAdminViewSet(BaseTestEnterpriseAPIViews):
    """
    Test PendingEnterpriseCustomerUserViewSet and LinkLearnersSerializer
    """

    def create_ent_user(self, user_exists, ecu_exists, pending_ecu_exists, user_email, enterprise_customer):
        """
        Creates enterprise users or pending users
        """
        user = None
        if user_exists:
            user = factories.UserFactory(email=user_email)
            if ecu_exists:
                factories.EnterpriseCustomerUserFactory(user_id=user.id, enterprise_customer=enterprise_customer)

        if pending_ecu_exists:
            factories.PendingEnterpriseCustomerUserFactory(
                user_email=user_email, enterprise_customer=enterprise_customer
            )
        return user

    def setup_admin_user(self):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    @ddt.data(
        {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True, 'status_code': 201},
        {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False, 'status_code': 201},
        {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False, 'status_code': 201},
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_user_creation(
            self,
            user_exists,
            ecu_exists,
            pending_ecu_exists,
            status_code):
        """
        Make sure service users can post new PendingEnterpriseCustomerUsers.
        """

        # create user making the request
        self.setup_admin_user()

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        # Fake enterprise admin permissions
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        user = self.create_ent_user(
            user_exists=user_exists,
            ecu_exists=ecu_exists,
            pending_ecu_exists=pending_ecu_exists,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        assert response.status_code == status_code
        response = self.load_json(response.content)
        self.assertDictEqual(data, response)
        if not user_exists:
            assert PendingEnterpriseCustomerUser.objects.get(
                user_email=new_user_email, enterprise_customer=enterprise_customer
            )
        else:
            assert EnterpriseCustomerUser.objects.get(
                user_id=user.id, enterprise_customer=enterprise_customer, active=user.is_active
            )

    @ddt.data(
        {'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False, 'status_code': 204},
        {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True, 'status_code': 204},
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_user_creation_no_user_created(
        self,
        user_exists,
        ecu_exists,
        pending_ecu_exists,
        status_code
    ):
        """
        Make sure service users can post new PendingEnterpriseCustomerUsers.
        """

        # create user making the request
        self.setup_admin_user()

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        # Fake enterprise admin permissions
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        self.create_ent_user(
            user_exists=user_exists,
            ecu_exists=ecu_exists,
            pending_ecu_exists=pending_ecu_exists,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        assert response.status_code == status_code
        assert not response.content

    def test_post_pending_enterprise_customer_unauthorized_user(self):
        # create user making the request
        self.setup_admin_user()

        # create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        self.create_ent_user(
            user_exists=False,
            ecu_exists=False,
            pending_ecu_exists=False,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        assert response.status_code == 403

    def test_post_pending_enterprise_customer_empty_bulk_payload(self):
        # create user making the request
        self.setup_admin_user()

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        # Fake enterprise admin permissions
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ent_uuid)

        route = reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid})
        response = self.client.post(
            settings.TEST_SERVER + route,
            data=[],
            format='json',
        )
        assert response.status_code == 400
        assert response.json() == 'At least one user email is required.'

    def test_post_pending_enterprise_customer_user_authorized_for_different_enterprise(self):
        # create user making the request
        self.setup_admin_user()

        # create fake enterprise
        ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        # Fake enterprise admin permissions for different enterprise
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, fake.uuid4())

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': ent_uuid,
            'user_email': new_user_email,
        }

        # create preexisting user(s) as necessary
        self.create_ent_user(
            user_exists=False,
            ecu_exists=False,
            pending_ecu_exists=False,
            user_email=new_user_email,
            enterprise_customer=enterprise_customer,
        )

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        assert response.status_code == 403

    @ddt.data(
        ([{'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True}], 201),
        ([{'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': True},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': False},
          {'user_exists': True, 'ecu_exists': False, 'pending_ecu_exists': False}], 201),
        ([{'user_exists': True, 'ecu_exists': True, 'pending_ecu_exists': False},
          {'user_exists': False, 'ecu_exists': False, 'pending_ecu_exists': True}], 204)
    )
    @ddt.unpack
    def test_post_pending_enterprise_customer_multiple_customers(self, userlist, status_code):
        self.setup_admin_user()
        ent_uuid = fake.uuid4()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ent_uuid)
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        data = []
        users = []
        for idx, user in enumerate(userlist):
            user_email = 'new_user{}@example.com'.format(idx)
            data.append({
                'enterprise_customer': ent_uuid,
                'user_email': user_email
            })

            existing_user = self.create_ent_user(
                user_exists=user['user_exists'],
                ecu_exists=user['ecu_exists'],
                pending_ecu_exists=user['pending_ecu_exists'],
                user_email=user_email,
                enterprise_customer=enterprise_customer,
            )
            users.append({
                'user_exists': user['user_exists'],
                'user_email': user_email,
                'existing_user': existing_user
            })

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data,
            format='json',
        )
        assert response.status_code == status_code
        for user in users:
            # assert that the correct users were created
            if not user['user_exists']:
                assert PendingEnterpriseCustomerUser.objects.get(
                    user_email=user['user_email'], enterprise_customer=enterprise_customer
                )
            else:
                assert EnterpriseCustomerUser.objects.get(
                    user_id=user['existing_user'].id,
                    enterprise_customer=enterprise_customer,
                    active=user['existing_user'].is_active
                )

    def test_post_pending_enterprise_customer_user_cannot_create_users_for_different_enterprise(self):
        # create user making the request
        self.setup_admin_user()

        # Create fake enterprise
        ent_uuid = fake.uuid4()
        other_ent_uuid = fake.uuid4()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ent_uuid)
        factories.EnterpriseCustomerFactory(uuid=other_ent_uuid)
        # Fake enterprise admin permissions
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ent_uuid)

        new_user_email = 'newuser@example.com'
        # data to be passed to the request
        data = {
            'enterprise_customer': other_ent_uuid,
            'user_email': new_user_email,
        }

        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        # This should cause a validation error
        assert response.status_code == 400
        assert serializers.LinkLearnersSerializer.NOT_AUTHORIZED_ERROR in response.data['enterprise_customer'][0]
        assert PendingEnterpriseCustomerUser.objects.filter(
            user_email=new_user_email, enterprise_customer=enterprise_customer
        ).count() == 0

    def test_post_pending_enterprise_customer_user_logged_out(self):
        """
        Make sure users can't post PendingEnterpriseCustomerUsers when logged out.
        """
        self.client.logout()
        ent_uuid = fake.uuid4()
        data = {
            'enterprise_customer': ent_uuid,
            'username': self.user.username
        }
        response = self.client.post(
            settings.TEST_SERVER + reverse('link-pending-enterprise-learner', kwargs={'enterprise_uuid': ent_uuid}),
            data=data
        )
        assert response.status_code == 401


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerViewSet(BaseTestEnterpriseAPIViews):
    """
    Test enterprise customer view set.
    """
    @ddt.data(
        (
            factories.EnterpriseCustomerFactory,
            ENTERPRISE_CUSTOMER_LIST_ENDPOINT,
            itemgetter('uuid'),
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'active': True,
                'auth_org_id': 'asdf3e2wdas',
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment', 'enable_audit_data_reporting': True,
                'site__domain': 'example.com', 'site__name': 'example.com',
                'contact_email': 'fake@example.com', 'sender_alias': 'Test Sender Alias',
                'reply_to': 'fake_reply@example.com', 'hide_labor_market_data': False,
                'modified': '2021-10-20T19:01:31Z',
            }],
            [{
                'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                'slug': TEST_SLUG, 'active': True,
                'auth_org_id': 'asdf3e2wdas',
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': get_default_branding_object(FAKE_UUIDS[0], TEST_SLUG),
                'identity_provider': None,
                'enable_audit_enrollment': False,
                'replace_sensitive_sso_username': False, 'enable_portal_code_management_screen': False,
                'sync_learner_profile_data': False,
                'enable_audit_data_reporting': True,
                'enable_learner_portal': True,
                'enable_learner_portal_offers': False,
                'enable_portal_learner_credit_management_screen': False,
                'enable_executive_education_2U_fulfillment': False,
                'enable_portal_reporting_config_screen': False,
                'enable_portal_saml_configuration_screen': False,
                'contact_email': 'fake@example.com',
                'enable_portal_subscription_management_screen': False,
                'hide_course_original_price': False,
                'enable_analytics_screen': True,
                'enable_integrated_customer_learner_portal_search': True,
                'enable_portal_lms_configurations_screen': False,
                'sender_alias': 'Test Sender Alias',
                'identity_providers': [],
                'enterprise_customer_catalogs': [],
                'reply_to': 'fake_reply@example.com',
                'enterprise_notification_banner': {'title': '', 'text': ''},
                'hide_labor_market_data': False,
                'modified': '2021-10-20T19:01:31Z',
                'enable_universal_link': False,
                'enable_browse_and_request': False,
                'admin_users': []
            }],
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            ENTERPRISE_LEARNER_LIST_ENDPOINT,
            itemgetter('user_id'),
            [{
                'id': 1, 'user_id': 0, 'created': '2021-10-20T19:01:31Z',
                'enterprise_customer__modified': '2021-10-20T19:01:31Z',
                'enterprise_customer__uuid': FAKE_UUIDS[0],
                'enterprise_customer__name': 'Test Enterprise Customer',
                'enterprise_customer__slug': TEST_SLUG,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com',
                'enterprise_customer__site__name': 'example.com',
                'enterprise_customer__contact_email': 'fake@example.com',
                'enterprise_customer__sender_alias': 'Test Sender Alias',
                'enterprise_customer__reply_to': 'fake_reply@example.com',
                'enterprise_customer__hide_labor_market_data': False,
                'enterprise_customer__auth_org_id': 'asdf3e2wdas',
            }],
            [{
                'id': 1,
                'enterprise_customer': {
                    'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer',
                    'slug': TEST_SLUG, 'active': True, 'auth_org_id': 'asdf3e2wdas',
                    'site': {
                        'domain': 'example.com', 'name': 'example.com'
                    },
                    'enable_data_sharing_consent': True,
                    'enforce_data_sharing_consent': 'at_enrollment',
                    'branding_configuration': get_default_branding_object(FAKE_UUIDS[0], TEST_SLUG),
                    'identity_provider': None, 'enable_audit_enrollment': False,
                    'replace_sensitive_sso_username': False, 'enable_portal_code_management_screen': False,
                    'sync_learner_profile_data': False, 'enable_audit_data_reporting': False,
                    'enable_learner_portal': True, 'enable_learner_portal_offers': False,
                    'enable_portal_learner_credit_management_screen': False,
                    'enable_executive_education_2U_fulfillment': False,
                    'enable_portal_reporting_config_screen': False,
                    'enable_portal_saml_configuration_screen': False,
                    'contact_email': 'fake@example.com',
                    'enable_portal_subscription_management_screen': False,
                    'hide_course_original_price': False, 'enable_analytics_screen': True,
                    'enable_integrated_customer_learner_portal_search': True,
                    'enable_portal_lms_configurations_screen': False,
                    'sender_alias': 'Test Sender Alias', 'identity_providers': [],
                    'enterprise_customer_catalogs': [], 'reply_to': 'fake_reply@example.com',
                    'enterprise_notification_banner': {'title': '', 'text': ''},
                    'hide_labor_market_data': False, 'modified': '2021-10-20T19:01:31Z',
                    'enable_universal_link': False, 'enable_browse_and_request': False,
                    'admin_users': [],
                },
                'active': True, 'user_id': 0, 'user': None,
                'data_sharing_consent_records': [], 'groups': [],
                'created': '2021-10-20T19:01:31Z', 'invite_key': None, 'role_assignments': [],
            }],
        ),
        (
            factories.EnterpriseCourseEnrollmentFactory,
            ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT,
            itemgetter('enterprise_customer_user'),
            [{
                'enterprise_customer_user__id': 1,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
                'created': '2021-10-20T19:01:31Z',
                'unenrolled_at': None,
            }],
            [{
                'enterprise_customer_user': 1,
                'course_id': 'course-v1:edX+DemoX+DemoCourse',
                'created': '2021-10-20T19:01:31Z',
                'unenrolled_at': None,
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
                'enterprise_customer__slug': TEST_SLUG,
                'enterprise_customer__active': True, 'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com',
                'enterprise_customer__site__name': 'example.com',
                'enterprise_customer__contact_email': 'fake@example.com',
                'enterprise_customer__sender_alias': 'Test Sender Alias',
                'enterprise_customer__reply_to': 'fake_reply@example.com',
                'enterprise_customer__hide_labor_market_data': False,
                'enterprise_customer__modified': '2021-10-20T19:01:31Z',
                'enterprise_customer__auth_org_id': 'asdf3e2wdas',
            }],
            [{
                'uuid': FAKE_UUIDS[1], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'active': True,
                'auth_org_id': 'asdf3e2wdas',
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': get_default_branding_object(FAKE_UUIDS[1], TEST_SLUG),
                'identity_provider': FAKE_UUIDS[0], 'enable_audit_enrollment': False,
                'replace_sensitive_sso_username': False, 'enable_portal_code_management_screen': False,
                'sync_learner_profile_data': False,
                'enable_audit_data_reporting': False,
                'enable_learner_portal': True,
                'enable_learner_portal_offers': False,
                'enable_portal_learner_credit_management_screen': False,
                'enable_executive_education_2U_fulfillment': False,
                'enable_portal_reporting_config_screen': False,
                'enable_portal_saml_configuration_screen': False,
                'contact_email': 'fake@example.com',
                'enable_portal_subscription_management_screen': False,
                'hide_course_original_price': False,
                'enable_analytics_screen': True,
                'enable_integrated_customer_learner_portal_search': True,
                'enable_portal_lms_configurations_screen': False,
                'sender_alias': 'Test Sender Alias',
                'identity_providers': [
                    {
                        "provider_id": FAKE_UUIDS[0],
                        "default_provider": False,
                    },
                ],
                'enterprise_customer_catalogs': [],
                'reply_to': 'fake_reply@example.com',
                'enterprise_notification_banner': {'title': '', 'text': ''},
                'hide_labor_market_data': False,
                'modified': '2021-10-20T19:01:31Z',
                'enable_universal_link': False,
                'enable_browse_and_request': False,
                'admin_users': [],
            }],
        ),
        (
            factories.EnterpriseCustomerCatalogFactory,
            ENTERPRISE_CUSTOMER_LIST_ENDPOINT,
            itemgetter('uuid'),
            [{
                'uuid': FAKE_UUIDS[0],
                'enterprise_customer__uuid': FAKE_UUIDS[1],
                'enterprise_customer__name': 'Test Enterprise Customer',
                'enterprise_customer__slug': TEST_SLUG,
                'enterprise_customer__active': True,
                'enterprise_customer__enable_data_sharing_consent': True,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'enterprise_customer__site__domain': 'example.com',
                'enterprise_customer__site__name': 'example.com',
                'enterprise_customer__contact_email': 'fake@example.com',
                'enterprise_customer__sender_alias': 'Test Sender Alias',
                'enterprise_customer__reply_to': 'fake_reply@example.com',
                'enterprise_customer__hide_labor_market_data': False,
                'enterprise_customer__modified': '2021-10-20T19:01:31Z',
                'enterprise_customer__auth_org_id': 'asdf3e2wdas',
            }],
            [{
                'uuid': FAKE_UUIDS[1], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
                'active': True, 'auth_org_id': 'asdf3e2wdas',
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': get_default_branding_object(FAKE_UUIDS[1], TEST_SLUG),
                'identity_provider': None,
                'enable_audit_enrollment': False,
                'replace_sensitive_sso_username': False,
                'enable_portal_code_management_screen': False,
                'sync_learner_profile_data': False,
                'enable_audit_data_reporting': False,
                'enable_learner_portal': True,
                'enable_learner_portal_offers': False,
                'enable_portal_learner_credit_management_screen': False,
                'enable_executive_education_2U_fulfillment': False,
                'enable_portal_reporting_config_screen': False,
                'enable_portal_saml_configuration_screen': False,
                'contact_email': 'fake@example.com',
                'enable_portal_subscription_management_screen': False,
                'hide_course_original_price': False,
                'enable_analytics_screen': True,
                'enable_integrated_customer_learner_portal_search': True,
                'enable_portal_lms_configurations_screen': False,
                'sender_alias': 'Test Sender Alias',
                'identity_providers': [],
                'enterprise_customer_catalogs': [FAKE_UUIDS[0]],
                'reply_to': 'fake_reply@example.com',
                'enterprise_notification_banner': {'title': '', 'text': ''},
                'hide_labor_market_data': False,
                'modified': '2021-10-20T19:01:31Z',
                'enable_universal_link': False,
                'enable_browse_and_request': False,
                'admin_users': [],
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
                'primary_color': '#000000',
                'secondary_color': '#ffffff',
                'tertiary_color': '#888888',
            }],
            [{
                'enterprise_customer': FAKE_UUIDS[0],
                'enterprise_slug': TEST_SLUG,
                'logo': settings.LMS_ROOT_URL + settings.MEDIA_URL + 'enterprise/branding/1/1_logo.png',
                'primary_color': '#000000',
                'secondary_color': '#ffffff',
                'tertiary_color': '#888888',
            }],
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.utils.get_logo_url')
    def test_api_views(self, factory, url, sorting_key, model_items, expected_json, mock_get_logo_url):
        """
        Make sure API end point returns all of the expected fields.
        """
        mock_get_logo_url.return_value = 'http://fake.url'
        self.create_items(factory, model_items)
        response = self.client.get(settings.TEST_SERVER + url)
        response = self.load_json(response.content)
        assert sorted(expected_json, key=sorting_key) == sorted(response['results'], key=sorting_key)

    def test_enterprise_customer_basic_list(self):
        """
            Test basic list endpoint of enterprise_customers
        """
        url = urljoin(settings.TEST_SERVER, ENTERPRISE_CUSTOMER_BASIC_LIST_ENDPOINT)
        enterprise_customers = [
            {
                'name': FAKER.company(),  # pylint: disable=no-member
                'uuid': str(uuid.uuid4())
            }
            for _ in range(15)
        ]
        self.create_items(factories.EnterpriseCustomerFactory, enterprise_customers)
        # now replace 'uuid' key with 'id'  to match with response.
        for enterprise_customer in enterprise_customers:
            enterprise_customer['id'] = enterprise_customer.pop("uuid")
        sorted_enterprise_customers = sorted(enterprise_customers, key=itemgetter('name'))

        response = self.client.get(url)
        assert sorted_enterprise_customers == self.load_json(response.content)

        # test startswith param
        startswith = 'a'
        startswith_enterprise_customers = [
            customer for customer in sorted_enterprise_customers if customer['name'].lower().startswith(startswith)
        ]
        response = self.client.get(url, {'startswith': startswith})
        assert startswith_enterprise_customers == self.load_json(response.content)

        # test name_or_uuid param
        name_or_uuid = enterprise_customers[0]['name']
        name_or_uuid_enterprise_customers = [
            customer for customer in sorted_enterprise_customers if customer['name'] == name_or_uuid
        ]
        response = self.client.get(url, {'name_or_uuid': name_or_uuid})
        assert name_or_uuid_enterprise_customers == self.load_json(response.content)

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
        # Staff user with group permission filtering on non existent enterprise id.
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
    @mock.patch('enterprise.utils.get_logo_url')
    def test_enterprise_customer_with_access_to(
            self,
            is_staff,
            is_linked_to_enterprise,
            user_groups,
            query_params,
            has_access_to_enterprise,
            expected_error,
            mock_get_logo_url,
    ):
        """
        ``enterprise_customer``'s detail list endpoint ``with_access_to`` should validate permissions
         and serialize the ``EnterpriseCustomer`` objects the user has access to.
        """
        mock_get_logo_url.return_value = 'http://fake.url'
        enterprise_customer_data = {
            'uuid': FAKE_UUIDS[0], 'name': 'Test Enterprise Customer', 'slug': TEST_SLUG,
            'active': True, 'enable_data_sharing_consent': True,
            'enforce_data_sharing_consent': 'at_enrollment', 'enable_portal_code_management_screen': True,
            'enable_portal_reporting_config_screen': False,
            'enable_portal_saml_configuration_screen': False,
            'enable_portal_lms_configurations_screen': False,
            'enable_universal_link': False,
            'enable_browse_and_request': False,
            'site__domain': 'example.com', 'site__name': 'example.com',
            'enable_portal_subscription_management_screen': False,
            'enable_analytics_screen': False,
            'contact_email': 'fake@example.com',
            'sender_alias': 'Test Sender Alias',
            'reply_to': 'fake_reply@example.com',
            'hide_labor_market_data': False,
            'modified': '2021-10-20T19:32:12Z',
            'auth_org_id': 'a34awed234'
        }
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_customer_data)

        # creating a non staff user so verify the insufficient permission conditions.
        user = factories.UserFactory(username='test_user', is_active=True, is_staff=is_staff)
        user.set_password('test_password')
        user.save()

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
                'active': True,
                'auth_org_id': enterprise_customer_data.get('auth_org_id'),
                'site': {
                    'domain': 'example.com', 'name': 'example.com'
                },
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment',
                'branding_configuration': get_default_branding_object(FAKE_UUIDS[0], TEST_SLUG),
                'identity_provider': None,
                'enable_audit_enrollment': False,
                'replace_sensitive_sso_username': False,
                'enable_portal_code_management_screen': True,
                'sync_learner_profile_data': False,
                'enable_audit_data_reporting': False,
                'enable_learner_portal': True,
                'enable_learner_portal_offers': False,
                'enable_portal_learner_credit_management_screen': False,
                'enable_executive_education_2U_fulfillment': False,
                'enable_portal_reporting_config_screen': False,
                'enable_portal_saml_configuration_screen': False,
                'contact_email': 'fake@example.com',
                'enable_portal_subscription_management_screen': False,
                'hide_course_original_price': False,
                'enable_analytics_screen': False,
                'enable_integrated_customer_learner_portal_search': True,
                'enable_portal_lms_configurations_screen': False,
                'sender_alias': 'Test Sender Alias',
                'identity_providers': [],
                'enterprise_customer_catalogs': [],
                'reply_to': 'fake_reply@example.com',
                'enterprise_notification_banner': {'title': '', 'text': ''},
                'hide_labor_market_data': False,
                'modified': '2021-10-20T19:32:12Z',
                'enable_universal_link': False,
                'enable_browse_and_request': False,
                'admin_users': []
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
                'primary_color': '#000000',
                'secondary_color': '#ffffff',
                'tertiary_color': '#888888',
            },
            {
                'enterprise_customer__uuid': FAKE_UUIDS[1],
                'enterprise_customer__slug': 'another-slug',
                'logo': 'enterprise/branding/2/2_logo.png',
                'primary_color': '#000000',
                'secondary_color': '#ffffff',
                'tertiary_color': '#888888',
            },
        ]
        expected_item = {
            'enterprise_customer': FAKE_UUIDS[0],
            'enterprise_slug': TEST_SLUG,
            'logo': settings.LMS_ROOT_URL + settings.MEDIA_URL + 'enterprise/branding/1/1_logo.png',
            'primary_color': '#000000',
            'secondary_color': '#ffffff',
            'tertiary_color': '#888888',
        }
        self.create_items(factory, model_items)
        response = self.client.get(settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BRANDING_DETAIL_ENDPOINT)
        response = self.load_json(response.content)
        assert expected_item == response

    @ddt.data(
        # Note that for admins, the specific enterprise_uuid_for_role is irrelevant because creation is allowed for
        # anybody that is admin for at least one enterprise customer.
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[0], 201),
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[1], 201),
        # But of course, learners should not have access.
        (ENTERPRISE_LEARNER_ROLE, FAKE_UUIDS[0], 403),
    )
    @ddt.unpack
    def test_create(self, enterprise_role, enterprise_uuid_for_role, expected_status_code):
        """
        Test that ``EnterpriseCustomer`` can be created by admins of the enterprise.
        """
        self.set_jwt_cookie(enterprise_role, str(enterprise_uuid_for_role))

        response = self.client.post(ENTERPRISE_CUSTOMER_LIST_ENDPOINT, {
            'name': 'Test Create Customer',
            'slug': 'test-create-customer',
            'site': {'domain': 'example.com'},
        }, format='json')

        assert response.status_code == expected_status_code

        if expected_status_code == 201:
            # First, smoke check the response body:
            assert response.json()['name'] == 'Test Create Customer'
            assert response.json()['slug'] == 'test-create-customer'
            assert response.json()['site'] == {'domain': 'example.com', 'name': 'example.com'}
            # Then, look in the database to confirm the customer was created:
            enterprise_customer = EnterpriseCustomer.objects.get(slug='test-create-customer')
            assert enterprise_customer.name == 'Test Create Customer'

    def test_create_missing_site(self):
        """
        Test creating an ``EnterpriseCustomer`` with missing/invalid site argument.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(FAKE_UUIDS[0]))

        response = self.client.post(ENTERPRISE_CUSTOMER_LIST_ENDPOINT, {
            'name': 'Test Create Customer',
            'slug': 'test-create-customer',
        }, format='json')

        assert response.status_code == 400
        assert response.json() == {'site': ['This field is required.']}

    def test_create_missing_site_domain(self):
        """
        Test creating an ``EnterpriseCustomer`` with missing/invalid site argument.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(FAKE_UUIDS[0]))

        response = self.client.post(ENTERPRISE_CUSTOMER_LIST_ENDPOINT, {
            'name': 'Test Create Customer',
            'slug': 'test-create-customer',
            'site': {'foo': 'bar'},
        }, format='json')

        assert response.status_code == 400
        assert response.json() == {'site': {'domain': 'This field is required.'}}

    def test_create_non_existent_site(self):
        """
        Test creating an ``EnterpriseCustomer`` with a non-existent site.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(FAKE_UUIDS[0]))

        response = self.client.post(ENTERPRISE_CUSTOMER_LIST_ENDPOINT, {
            'name': 'Test Create Customer',
            'slug': 'test-create-customer',
            'site': {'domain': 'does.not.exist'},
        }, format='json')

        assert response.status_code == 400
        assert response.json() == {'site': {'domain': 'No Site with the provided domain was found.'}}

    @ddt.data(
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[0], 200),
        (ENTERPRISE_LEARNER_ROLE, FAKE_UUIDS[0], 403),
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[1], 403)
    )
    @ddt.unpack
    def test_partial_update(self, enterprise_role, enterprise_uuid_for_role, expected_status_code):
        """
        Test that ``EnterpriseCustomer`` can be updated by admins of the enterprise.
        """

        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0], slug='test-enterprise-slug')

        self.set_jwt_cookie(enterprise_role, str(enterprise_uuid_for_role))

        response = self.client.patch(ENTERPRISE_CUSTOMER_DETAIL_ENDPOINT, {
            "slug": 'new-slug'
        })

        assert response.status_code == expected_status_code

        if expected_status_code == 200:
            enterprise_customer.refresh_from_db()
            assert enterprise_customer.slug == 'new-slug'

    @ddt.data(
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[0], False, 200),
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[0], True, 200),
        (ENTERPRISE_LEARNER_ROLE, FAKE_UUIDS[0], False, 403),
        (ENTERPRISE_ADMIN_ROLE, FAKE_UUIDS[1], False, 403),
    )
    @ddt.unpack
    def test_unlink_users(self, enterprise_role, enterprise_uuid_for_role, is_relinkable, expected_status_code):
        """
        Test that enterprise admins can unlink users from enterprise.
        """

        email_1 = 'abc@test.com'
        email_2 = 'efg@test.com'

        user_1 = factories.UserFactory(email=email_1)
        user_2 = factories.UserFactory(email=email_2)

        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0], slug='test-enterprise-slug')

        enterprise_customer_user_1 = factories.EnterpriseCustomerUserFactory(
            user_id=user_1.id,
            enterprise_customer=enterprise_customer
        )
        enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(
            user_id=user_2.id,
            enterprise_customer=enterprise_customer
        )

        assert enterprise_customer_user_1.linked is True
        assert enterprise_customer_user_2.linked is True

        self.set_jwt_cookie(enterprise_role, str(enterprise_uuid_for_role))

        response = self.client.post(ENTERPRISE_CUSTOMER_UNLINK_USERS_ENDPOINT, {
            "user_emails": [email_1, email_2],
            "is_relinkable": is_relinkable
        })

        assert response.status_code == expected_status_code

        if expected_status_code == 200:
            enterprise_customer_user_1.refresh_from_db()
            enterprise_customer_user_2.refresh_from_db()
            assert enterprise_customer_user_1.linked is False
            assert enterprise_customer_user_2.linked is False
            assert enterprise_customer_user_2.is_relinkable == is_relinkable
            assert enterprise_customer_user_2.is_relinkable == is_relinkable


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerCatalogWriteViewSet(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCustomerCatalogWriteViewSet
    """
    @ddt.data(
        (False, 403),
        (True, 201),
    )
    @ddt.unpack
    def test_create_catalog(self, is_staff, expected_status_code):
        """
        Test that a catalog can be created
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        enterprise_catalog_query = factories.EnterpriseCatalogQueryFactory()

        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(enterprise_customer.uuid))
        self.user.is_staff = is_staff
        self.user.save()

        response = self.client.post(ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT, {
            "title": "Test Catalog",
            "enterprise_customer": str(enterprise_customer.uuid),
            "enterprise_catalog_query": str(enterprise_catalog_query.id),
        }, format='json')
        response_output = self.load_json(response.content)

        assert response.status_code == expected_status_code

        if expected_status_code == 201:
            assert response_output['title'] == 'Test Catalog'
            assert response_output['enterprise_customer'] == str(enterprise_customer.uuid)
        if expected_status_code == 403:
            assert response_output['detail'] == 'You do not have permission to perform this action.'

    def test_create_existing_catalog(self):
        """
        Test that a catalog cannot be created if it already exists and returns an existing catalog
        This is to prevent duplicate catalogs from being created using an idempotent strategy
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        enterprise_catalog_query = factories.EnterpriseCatalogQueryFactory()

        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(enterprise_customer.uuid))
        self.user.is_staff = True
        self.user.save()

        response = self.client.post(ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT, {
            "title": "Test Catalog",
            "enterprise_customer": str(enterprise_customer.uuid),
            "enterprise_catalog_query": str(enterprise_catalog_query.id),
        }, format='json')
        response_output = self.load_json(response.content)

        duplicate_response = self.client.post(ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT, {
            "title": "Test Catalog 2",
            "enterprise_customer": str(enterprise_customer.uuid),
            "enterprise_catalog_query": str(enterprise_catalog_query.id),
        }, format='json')
        duplicate_response_output = self.load_json(duplicate_response.content)

        response_all = self.client.get(ENTERPRISE_CATALOGS_DETAIL_ENDPOINT)
        response_all_output = self.load_json(response_all.content)

        assert len(response_all_output) == 1
        assert response.status_code == 201
        assert response_output['title'] == 'Test Catalog'
        assert response_output['enterprise_customer'] == str(enterprise_customer.uuid)
        assert duplicate_response.status_code == 200
        assert duplicate_response_output['title'] == 'Test Catalog'
        assert duplicate_response_output['enterprise_customer'] == str(enterprise_customer.uuid)

    def test_create_catalog_incorrect_data(self):
        """
        Test that a catalog cannot be created with a non-existent customer uuid
        """
        enterprise_customer = {
            'uuid': FAKE_UUIDS[0]
        }
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(enterprise_customer['uuid']))
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT, {
            "title": "Test Catalog",
            "enterprise_customer": str(enterprise_customer['uuid']),
        }, format='json')
        response_output = self.load_json(response.content)
        assert response.status_code == 400
        if response.status_code == 400:
            assert "Invalid pk" in response_output['enterprise_customer'][0]

    def test_partially_update_enterprise_customer_catalog(self, is_staff, expected_status_code):
        """
        Test that a catalog can be partially updated
        """
        enterprise_customer_catalog_uuid = {
            'uuid': FAKE_UUIDS[0]
        }
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(enterprise_customer.uuid))
        self.user.is_staff = is_staff
        self.user.save()

        response = self.client.patch(ENTERPRISE_CUSTOMER_CATALOG_ENDPOINT, {
            "title": "Test title update",
            "uuid": str(enterprise_customer_catalog_uuid['uuid']),
        }, format='json')
        response_output = self.load_json(response.content)

        assert response.status_code == expected_status_code

        if expected_status_code == 200:
            assert response_output['title'] == 'Test title update'
            assert response_output['enterprise_customer'] == str(enterprise_customer.uuid)
            assert response_output['uuid'] == str(enterprise_customer_catalog_uuid['uuid'])
        if expected_status_code == 404:
            assert response_output['detail'] == 'Could not find catalog uuid'


@ddt.ddt
@mark.django_db
class TestEntepriseCustomerCatalogs(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCustomerCatalogViewSet
    """
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
                add_utm_info=False,
                count=3,
            ),
        ),
        (
            True,
            False,
            fake_enterprise_api.build_fake_enterprise_catalog_detail(
                paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                include_enterprise_context=True,
                add_utm_info=False,
                count=3,
            ),
        ),
        (
            True,
            True,
            fake_enterprise_api.build_fake_enterprise_catalog_detail(
                paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                include_enterprise_context=True,
                add_utm_info=False,
                count=3,
            ),
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            enterprise_customer=enterprise_customer,
            title='All Content',
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

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            title='All Content',
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
            include_enterprise_context=True,
            add_utm_info=False,
            count=2,
        )
        assert response == expected_result

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            title='All Content',
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
            next_url=urljoin('http://testserver/', ENTERPRISE_CATALOGS_DETAIL_ENDPOINT) + '?page=3',
            add_utm_info=False,
            count=5,
        )
        assert response == expected_result

    @ddt.data(
        (False, {'course_run_ids': ['fake1', 'fake2']}, {}),
        (False, {'program_uuids': ['fake1', 'fake2']}, {}),
        (
            True,
            {
                'course_run_ids': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ]
            },
            {
                'results': [
                    fake_catalog_api.FAKE_COURSE_RUN,
                    fake_catalog_api.FAKE_COURSE_RUN2
                ]
            }
        ),
        (
            True,
            {
                'program_uuids': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            },
            {
                'results': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2
                ]
            }
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            get_catalog_results=mock.Mock(return_value=search_results)
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
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            },
            enterprise_catalog_query=None,
        )

        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(return_value={})
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
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_course_run_detail(
            self,
            is_staff,
            is_linked_to_enterprise,
            is_course_run_in_catalog,
            mocked_course_run,
            expected_result,
            mock_catalog_api_client,
            mock_ent_catalog_api_client
    ):
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
        search_results = {}
        if is_course_run_in_catalog:
            search_results = {'results': [fake_catalog_api.FAKE_COURSE_RUN]}
        mock_ent_catalog_api_client.return_value.contains_content_items.return_value = is_course_run_in_catalog
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(return_value=search_results),
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
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_course_detail(
            self,
            is_staff,
            is_linked_to_enterprise,
            is_course_in_catalog,
            mocked_course,
            expected_result,
            mock_catalog_api_client,
            mock_ent_catalog_api_client
    ):
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
        search_results = {}
        if is_course_in_catalog:
            search_results = {'results': [fake_catalog_api.FAKE_COURSE]}
        mock_ent_catalog_api_client.return_value.contains_content_items.return_value = is_course_in_catalog
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(return_value=search_results),
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
    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_enterprise_catalog_program_detail(
            self,
            is_staff,
            is_linked_to_enterprise,
            has_existing_catalog,
            is_program_in_catalog,
            mocked_program,
            expected_result,
            mock_catalog_api_client,
            mock_ent_catalog_api_client
    ):
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
        search_results = {}
        if is_program_in_catalog:
            search_results = {'results': [fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1]}
        mock_ent_catalog_api_client.return_value.contains_content_items.return_value = is_program_in_catalog
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(return_value=search_results),
            get_program_by_uuid=mock.Mock(return_value=mocked_program),
        )
        response = self.client.get(ENTERPRISE_CATALOGS_PROGRAM_ENDPOINT)
        response = self.load_json(response.content)

        assert response == expected_result

    @ddt.data(
        (False, {'course_run_ids': ['fake1', 'fake2']}, {}),
        (False, {'program_uuids': ['fake1', 'fake2']}, {}),
        (
            True,
            {
                'course_run_ids': [
                    fake_catalog_api.FAKE_COURSE_RUN['key'],
                    fake_catalog_api.FAKE_COURSE_RUN2['key']
                ]
            },
            {
                'results': [
                    fake_catalog_api.FAKE_COURSE_RUN,
                    fake_catalog_api.FAKE_COURSE_RUN2
                ]
            }
        ),
        (
            True,
            {
                'program_uuids': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1['uuid'],
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2['uuid']
                ]
            },
            {
                'results': [
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
                    fake_catalog_api.FAKE_SEARCH_ALL_PROGRAM_RESULT_2
                ]
            }
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
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
            get_catalog_results=mock.Mock(return_value=search_results)
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


@ddt.ddt
@mark.django_db
class TestEnterpriesCustomerCourseEnrollments(BaseTestEnterpriseAPIViews):
    """
    Test the Enteprise Customer course enrollments detail route
    """

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
                'lms_user_id': 10,
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
                'lms_user_id': 10,
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
                'lms_user_id': 10,
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
            {'is_active': True, 'mode': VERIFIED_SUBSCRIPTION_COURSE_MODE},
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 10,
            }],
            [{
                'detail': (
                    'The user is already enrolled in the course course-v1:edX+DemoX+Demo_Course '
                    'in verified mode and cannot be enrolled in audit mode'
                )
            }],
        ),
        (
            True,
            True,
            {'is_active': False, 'mode': 'audit'},
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 10,
                'cohort': 'masters'
            }],
            [{
                'detail': (
                    'Auto-cohorting is not enabled for this enterprise'
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
                'lms_user_id': 10,
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
                'lms_user_id': 10,
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
                'lms_user_id': 10,
                'email_students': True
            }],
        ),
        (
            True,
            None,
            [{
                'course_mode': 'audit',
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 10,
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
                'course_mode': VERIFIED_SUBSCRIPTION_COURSE_MODE,
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 10,
            }],
        ),
        (
            True,
            {'is_active': False, 'mode': 'audit'},
            [{
                'course_mode': VERIFIED_SUBSCRIPTION_COURSE_MODE,
                'course_run_id': 'course-v1:edX+DemoX+Demo_Course',
                'lms_user_id': 10,
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
            True,
            enable_autocohorting=True
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
                    source=EnterpriseEnrollmentSource.get_source(EnterpriseEnrollmentSource.API)
                ).exists()
                enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.filter(
                    enterprise_customer_user__user_id=user.id,
                    course_id=payload.get('course_run_id'),
                    source=EnterpriseEnrollmentSource.get_source(EnterpriseEnrollmentSource.API)
                ).first()
                enterprise_customer = enterprise_course_enrollment.enterprise_customer_user.enterprise_customer
                mock_enrollment_client.return_value.get_course_enrollment.assert_called_once_with(
                    user.username, payload.get('course_run_id')
                )
                mock_enrollment_client.return_value.enroll_user_in_course.assert_called_once_with(
                    user.username,
                    payload.get('course_run_id'),
                    payload.get('course_mode'),
                    cohort=payload.get('cohort'),
                    enterprise_uuid=str(enterprise_customer.uuid)
                )
        elif 'user_email' in payload and payload.get('is_active', True):
            # If a new user given via for user_email, check that the appropriate objects were created.
            pending_ecu = PendingEnterpriseCustomerUser.objects.get(
                enterprise_customer=enterprise_customer,
                user_email=payload.get('user_email'),
            )

            assert pending_ecu is not None
            pending_enrollment = PendingEnrollment.objects.filter(
                user=pending_ecu,
                course_id=payload.get('course_run_id'),
                course_mode=payload.get('course_mode')
            )
            if payload.get('is_active', True):
                assert pending_enrollment[0]
                assert pending_enrollment[0].cohort_name == payload.get('cohort')
                assert pending_enrollment[0].source.slug == EnterpriseEnrollmentSource.API
            else:
                assert not pending_enrollment
            mock_enrollment_client.return_value.get_course_enrollment.assert_not_called()
            mock_enrollment_client.return_value.enroll_user_in_course.assert_not_called()
        elif 'user_email' in payload and not payload.get('is_active', True):
            with raises(PendingEnterpriseCustomerUser.DoesNotExist):
                # No Pending user should have been created in this case.
                PendingEnterpriseCustomerUser.objects.get(
                    user_email=payload.get('user_email'),
                    enterprise_customer=enterprise_customer
                )

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
        lms_user_id = 10
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
                side_effect=[None, {'is_active': True, 'mode': VERIFIED_SUBSCRIPTION_COURSE_MODE}]
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
        self.assertEqual(response_default['content-type'], 'application/json')

        response_json = self.client.get('/enterprise/api/v1/enterprise_catalogs.json')
        self.assertEqual(response_json['content-type'], 'application/json')

        response_xml = self.client.get('/enterprise/api/v1/enterprise_catalogs.xml')
        self.assertEqual(response_xml['content-type'], 'application/xml; charset=utf-8')


@ddt.ddt
@mark.django_db
class TestEnterpriseCatalogQueryViewSet(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCatalogQueryViewSet
    """
    catalog_query_content_filter = {
        "query_field": "query_data"
    }

    def setUp(self):
        """
        Test set up.
        """
        super().setUp()
        self.enterprise_catalog_query = factories.EnterpriseCatalogQueryFactory(
            content_filter=self.catalog_query_content_filter)

    def test_enterprise_catalog_query_list_response_formats(self):
        """
        ``enterprise_catalog_query``'s json responses verification.
        """
        response_default = self.client.get('/enterprise/api/v1/enterprise_catalog_query/')
        self.assertEqual(response_default['content-type'], 'application/json')

        response_json = self.client.get('/enterprise/api/v1/enterprise_catalog_query.json')
        self.assertEqual(response_json['content-type'], 'application/json')

    def test_enteprise_catalog_query_list(self):
        """
        ``enterprise_catalog_query``'s response when no catalog uuid is provided.
        """
        ENTERPRISE_CATALOG_QUERY_ENDPOINT = reverse('enterprise_catalog_query-list')
        response = self.client.get(ENTERPRISE_CATALOG_QUERY_ENDPOINT)
        self.assertEqual(response.status_code, 200)

    def test_enterprise_catalog_query_detail(self):
        """
        ``enterprise_catalog_query``'s response when a catalog uuid is provided.
        """

        ENTERPRISE_CATALOG_QUERY_ENDPOINT = reverse('enterprise_catalog_query-detail',
                                                    args=[self.enterprise_catalog_query.id])

        response = self.client.get(ENTERPRISE_CATALOG_QUERY_ENDPOINT)
        self.assertEqual(response.status_code, 200)

    def test_enterprise_catalog_query_detail_not_found(self):
        """
        ``enterprise_catalog_query``'s response when a catalog uuid is provided but not found.
        """
        ENTERPRISE_CATALOG_QUERY_ENDPOINT = reverse('enterprise_catalog_query-detail', args=[2])

        response = self.client.get(ENTERPRISE_CATALOG_QUERY_ENDPOINT)
        self.assertEqual(response.status_code, 404)

    def test_enterprise_catalog_query_detail_bad_uuid(self):
        """
        ``enterprise_catalog_query``'s response when a catalog uuid is provided but bad.
        """
        ENTERPRISE_CATALOG_QUERY_ENDPOINT = reverse('enterprise_catalog_query-detail', args=['bad-uuid'])

        response = self.client.get(ENTERPRISE_CATALOG_QUERY_ENDPOINT)
        self.assertEqual(response.status_code, 404)


@ddt.ddt
@mark.django_db
class TestRequestCodesEndpoint(BaseTestEnterpriseAPIViews):
    """
    Test CouponCodesView
    """

    REQUEST_CODES_ENDPOINT = reverse('request-codes')

    @mock.patch('django.core.mail.send_mail')
    @ddt.data(
        (
            # A valid request.
            {
                'email': 'johndoe@unknown.com',
                'enterprise_name': 'Oracle',
                'number_of_codes': '50',
                'notes': 'Here are helping notes',
            },
            {'email': 'johndoe@unknown.com', 'enterprise_name': 'Oracle', 'number_of_codes': '50',
             'notes': 'Here are helping notes'},
            200,
            None,
            True,
            'johndoe@unknown.com from Oracle has requested 50 additional codes. Please reach out to them.'
            '\nAdditional Notes:\nHere are helping notes.'.encode("unicode_escape").decode("utf-8")
        ),
        (
            # A valid request without codes
            {
                'email': 'johndoe@unknown.com',
                'enterprise_name': 'Oracle',
                'number_of_codes': None,
                'notes': 'Here are helping notes',
            },
            {'email': 'johndoe@unknown.com', 'enterprise_name': 'Oracle', 'number_of_codes': None,
             'notes': 'Here are helping notes'},
            200,
            None,
            True,
            'johndoe@unknown.com from Oracle has requested additional codes. Please reach out to them.'
            '\nAdditional Notes:\nHere are helping notes.'.encode("unicode_escape").decode("utf-8")
        ),
        (
            # A valid request without notes
            {
                'email': 'johndoe@unknown.com',
                'enterprise_name': 'Oracle',
                'number_of_codes': '50',
                'notes': None,
            },
            {'email': 'johndoe@unknown.com', 'enterprise_name': 'Oracle', 'number_of_codes': '50',
             'notes': None},
            200,
            None,
            True,
            'johndoe@unknown.com from Oracle has requested 50 additional codes. Please reach out to them.'
        ),
        (
            # A bad request due to a missing field
            {
                'email': 'johndoe@unknown.com',
                'number_of_codes': '50',
                'notes': 'Here are helping notes',
            },
            {'error': 'Some required parameter(s) missing: enterprise_name'},
            400,
            None,
            False,
            'johndoe@unknown.com from Oracle has requested 50 additional codes. Please reach out to them.'
            '\nAdditional Notes:\nHere are helping notes.'.encode("unicode_escape").decode("utf-8")
        ),
        (
            # Email send issue
            {
                'email': 'johndoe@unknown.com',
                'enterprise_name': 'Oracle',
                'number_of_codes': '50',
                'notes': 'Here are helping notes',
            },
            {'error': 'Request codes email could not be sent'},
            500,
            SMTPException(),
            True,
            'johndoe@unknown.com from Oracle has requested 50 additional codes. Please reach out to them.'
            '\nAdditional Notes:\nHere are helping notes.'.encode("unicode_escape").decode("utf-8")
        )
    )
    @ddt.unpack
    def test_post_request_codes(
            self,
            post_data,
            response_data,
            status_code,
            mock_side_effect,
            mail_attempted,
            expected_email_message,
            mock_send_mail,
    ):
        """
        Ensure endpoint response data and status codes.
        """
        mock_send_mail.side_effect = mock_side_effect
        response = self.client.post(
            settings.TEST_SERVER + self.REQUEST_CODES_ENDPOINT,
            data=json.dumps(post_data),
            content_type='application/json',
        )
        assert response.status_code == status_code
        response = self.load_json(response.content)

        self.assertDictEqual(response_data, response)
        if mail_attempted:
            mock_send_mail.assert_called_once()
            call_args = (str(w) for w in mock_send_mail.call_args_list)
            self.assertIn(expected_email_message, ''.join(call_args))
        else:
            mock_send_mail.assert_not_called()

    @mock.patch('enterprise.rules.crum.get_current_request')
    @mock.patch('django.core.mail.send_mail', mock.Mock(return_value={'status_code': status.HTTP_200_OK}))
    @ddt.data(
        (False, False, status.HTTP_403_FORBIDDEN),
        (False, True, status.HTTP_200_OK),
        (True, False, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_post_request_codes_permissions(self, implicit_perm, explicit_perm, expected_status, request_or_stub_mock):
        """
        Test that role base permissions works as expected.
        """
        user = factories.UserFactory(username='test_user', is_active=True, is_staff=False)
        user.set_password('test_password')
        user.save()
        client = APIClient()
        client.login(username='test_user', password='test_password')

        system_wide_role = ENTERPRISE_ADMIN_ROLE

        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(name=ENTERPRISE_DASHBOARD_ADMIN_ROLE)
        EnterpriseFeatureUserRoleAssignment.objects.create(user=user, role=feature_role_object)

        if implicit_perm is False:
            system_wide_role = 'role_with_no_mapped_permissions'

        if explicit_perm is False:
            EnterpriseFeatureUserRoleAssignment.objects.all().delete()

        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        post_data = {
            'email': 'johndoe@unknown.com',
            'enterprise_name': 'Oracle',
            'number_of_codes': '50',
        }
        response = client.post(
            settings.TEST_SERVER + self.REQUEST_CODES_ENDPOINT,
            data=json.dumps(post_data),
            content_type='application/json',
        )

        assert response.status_code == expected_status


@ddt.ddt
@mark.django_db
class TestEnterpriseSubsidyFulfillmentViewSet(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseSubsidyFulfillmentViewSet
    """

    def setUp(self):
        super().setUp()

        self._create_user_and_enterprise_customer('test_user', 'test_password')

        self.client = APIClient()
        self.client.login(username='test_user', password='test_password')
        self.set_jwt_cookie(ENTERPRISE_OPERATOR_ROLE, str(self.enterprise_customer.uuid))

        self.unenrolled_after_filter = f'?unenrolled_after={str(datetime.now() - timedelta(hours=24))}'

        self.course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_user,
            course_id=self.course_id,
        )
        self.licensed_course_enrollment = factories.LicensedEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=self.enterprise_course_enrollment,
        )
        self.learner_credit_course_enrollment = factories.LearnerCreditEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=self.enterprise_course_enrollment,
        )

        self.licensed_fulfillment_url = reverse(
            'enterprise-subsidy-fulfillment',
            kwargs={'fulfillment_source_uuid': str(self.licensed_course_enrollment.uuid)}
        )
        self.learner_credit_fulfillment_url = reverse(
            'enterprise-subsidy-fulfillment',
            kwargs={'fulfillment_source_uuid': str(self.learner_credit_course_enrollment.uuid)}
        )
        self.cancel_licensed_fulfillment_url = self.licensed_fulfillment_url + '/cancel-fulfillment'
        self.cancel_learner_credit_fulfillment_url = self.learner_credit_fulfillment_url + '/cancel-fulfillment'

    def _create_user_and_enterprise_customer(self, username, password):
        """
        Helper method to create the User and Enterprise Customer used in tests.
        """
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=False)
        self.user.set_password(password)
        self.user.save()

        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )

    def test_requested_recently_unenrolled_subsidy_fulfillment(self):
        """
        Test that we can successfully retrieve recently unenrolled subsidized enrollments.
        """
        second_enterprise_customer = factories.EnterpriseCustomerFactory()
        second_enterprise_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=second_enterprise_customer,
        )
        second_enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=second_enterprise_user,
            course_id=self.course_id,
            unenrolled_at=localized_utcnow(),
        )
        # Have a second enrollment that is under a different enterprise customer than the requesting
        # user. Because the requesting user is an operator user, they should be able to see this enrollment.
        second_lc_enrollment = factories.LearnerCreditEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=second_enterprise_course_enrollment,
        )

        self.enterprise_course_enrollment.unenrolled_at = localized_utcnow()
        self.enterprise_course_enrollment.save()
        response = self.client.get(
            reverse('enterprise-subsidy-fulfillment-unenrolled') + self.unenrolled_after_filter
        )

        lc_ent_user_1 = self.learner_credit_course_enrollment.enterprise_course_enrollment.enterprise_customer_user.id
        lc_ent_user_2 = second_lc_enrollment.enterprise_course_enrollment.enterprise_customer_user.id
        lc_unenrolled_date = self.learner_credit_course_enrollment.enterprise_course_enrollment.unenrolled_at.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert OrderedDict([
            ('enterprise_course_enrollment', OrderedDict([
                ('enterprise_customer_user', lc_ent_user_1),
                ('course_id', self.learner_credit_course_enrollment.enterprise_course_enrollment.course_id),
                ('unenrolled_at', lc_unenrolled_date),
                ('created', self.learner_credit_course_enrollment.enterprise_course_enrollment.created.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )),
            ])),
            ('transaction_id', self.learner_credit_course_enrollment.transaction_id),
            ('uuid', str(self.learner_credit_course_enrollment.uuid)),
        ]) in response.data
        assert OrderedDict([
            ('enterprise_course_enrollment', OrderedDict(
                [
                    ('enterprise_customer_user', lc_ent_user_2),
                    ('course_id', second_lc_enrollment.enterprise_course_enrollment.course_id),
                    ('unenrolled_at', second_lc_enrollment.enterprise_course_enrollment.modified.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )),
                    ('created', second_lc_enrollment.enterprise_course_enrollment.created.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )),
                ]
            )),
            ('transaction_id', second_lc_enrollment.transaction_id),
            ('uuid', str(second_lc_enrollment.uuid)),
        ]) in response.data
        assert len(response.data) == 2

    def test_recently_unenrolled_fulfillment_endpoint_can_filter_for_modified_after(self):
        """
        Test that unenrolled fulfillments older than 24 hours are not surfaced.
        """
        # You can force the modified date to be older than 24 hours by initializing the value
        old_enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_user,
            course_id=self.course_id + '2',
            unenrolled_at=localized_utcnow() - timedelta(days=5),
        )
        old_learner_credit_enrollment = factories.LearnerCreditEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=old_enterprise_course_enrollment,
        )
        response = self.client.get(
            reverse('enterprise-subsidy-fulfillment-unenrolled') + self.unenrolled_after_filter
        )
        assert response.data == []
        long_ago_filter = str((localized_utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        response = self.client.get(
            reverse(
                'enterprise-subsidy-fulfillment-unenrolled'
            ) + f'?unenrolled_after={long_ago_filter}'
        )

        ent_user = old_learner_credit_enrollment.enterprise_course_enrollment.enterprise_customer_user.id
        lc_unenrolled_at = old_learner_credit_enrollment.enterprise_course_enrollment.unenrolled_at.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert response.data == [
            OrderedDict([
                ('enterprise_course_enrollment', OrderedDict([
                    ('enterprise_customer_user', ent_user),
                    ('course_id', old_learner_credit_enrollment.enterprise_course_enrollment.course_id),
                    ('unenrolled_at', lc_unenrolled_at),
                    ('created', old_learner_credit_enrollment.enterprise_course_enrollment.created.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )),
                ])),
                ('transaction_id', old_learner_credit_enrollment.transaction_id),
                ('uuid', str(old_learner_credit_enrollment.uuid)),
            ]),
        ]

    def test_recently_unenrolled_licensed_fulfillment_object(self):
        """
        Test that the correct licensed fulfillment object is returned.
        """
        self.enterprise_course_enrollment.unenrolled_at = localized_utcnow()
        self.enterprise_course_enrollment.save()
        response = self.client.get(
            reverse('enterprise-subsidy-fulfillment-unenrolled') + self.unenrolled_after_filter
            + '&retrieve_licensed_enrollments=True'
        )
        ent_user = self.licensed_course_enrollment.enterprise_course_enrollment.enterprise_customer_user.id
        licensed_unenrolled_at = self.licensed_course_enrollment.enterprise_course_enrollment.unenrolled_at.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert response.data == [
            OrderedDict([
                ('enterprise_course_enrollment', OrderedDict([
                    ('enterprise_customer_user', ent_user),
                    ('course_id', self.licensed_course_enrollment.enterprise_course_enrollment.course_id),
                    ('unenrolled_at', licensed_unenrolled_at),
                    ('created', self.licensed_course_enrollment.enterprise_course_enrollment.created.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )),
                ])),
                ('license_uuid', str(self.licensed_course_enrollment.license_uuid)),
                ('uuid', str(self.licensed_course_enrollment.uuid)),
            ]),
        ]

    def test_successful_retrieve_licensed_enrollment(self):
        """
        Test that we can successfully retrieve a licensed enrollment.
        """
        response = self.client.get(
            settings.TEST_SERVER + self.licensed_fulfillment_url,
        )
        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()
        assert response_json == {
            'license_uuid': str(self.licensed_course_enrollment.license_uuid),
            'enterprise_course_enrollment': {
                'enterprise_customer_user': self.enterprise_user.id,
                'course_id': self.enterprise_course_enrollment.course_id,
                'unenrolled_at': self.enterprise_course_enrollment.unenrolled_at,
                'created': self.enterprise_course_enrollment.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            'uuid': str(self.licensed_course_enrollment.uuid),
        }

    def test_successful_retrieve_learner_credit_enrollment(self):
        """
        Test that we can successfully retrieve a learner credit enrollment.
        """
        response = self.client.get(
            settings.TEST_SERVER + self.learner_credit_fulfillment_url,
        )

        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()
        assert response_json == {
            'transaction_id': str(self.learner_credit_course_enrollment.transaction_id),
            'enterprise_course_enrollment': {
                'enterprise_customer_user': self.enterprise_user.id,
                'course_id': self.enterprise_course_enrollment.course_id,
                'unenrolled_at': self.enterprise_course_enrollment.unenrolled_at,
                'created': self.enterprise_course_enrollment.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            'uuid': str(self.learner_credit_course_enrollment.uuid),
        }

    def test_retrieve_nonexistent_enrollment(self):
        """
        Test that we get a 404 when trying to retrieve a nonexistent enrollment.
        """
        response = self.client.get(
            settings.TEST_SERVER + reverse(
                'enterprise-subsidy-fulfillment',
                kwargs={'fulfillment_source_uuid': str(uuid.uuid4())}
            ),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unsupported_methods(self):
        """
        Ensure that we get a 405 when trying to use unsupported methods.
        """
        create_response = self.client.post(
            settings.TEST_SERVER + self.licensed_fulfillment_url,
        )
        assert create_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        delete_response = self.client.delete(
            settings.TEST_SERVER + self.licensed_fulfillment_url,
        )
        assert delete_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        update_response = self.client.put(
            settings.TEST_SERVER + self.licensed_fulfillment_url,
        )
        assert update_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @mock.patch("enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api")
    def test_successful_cancel_fulfillment(self, mock_enrollment_api):
        """
        Test that we can successfully cancel both licensed and learner credit fulfillments.
        """
        mock_enrollment_api.update_enrollment.return_value = mock.Mock()
        self.licensed_course_enrollment.is_revoked = False
        self.licensed_course_enrollment.save()
        response = self.client.post(
            settings.TEST_SERVER + self.cancel_licensed_fulfillment_url,
        )

        assert response.status_code == status.HTTP_200_OK
        self.licensed_course_enrollment.refresh_from_db()
        assert self.licensed_course_enrollment.is_revoked
        mock_enrollment_api.update_enrollment.assert_called_once()
        assert mock_enrollment_api.update_enrollment.call_args.args == (
            self.enterprise_course_enrollment.enterprise_customer_user.user.username,
            self.enterprise_course_enrollment.course_id,
        )
        assert mock_enrollment_api.update_enrollment.call_args.kwargs == {
            'is_active': False,
        }

        mock_enrollment_api.reset_mock()

        self.learner_credit_course_enrollment.is_revoked = False
        self.learner_credit_course_enrollment.save()
        response = self.client.post(
            settings.TEST_SERVER + self.cancel_learner_credit_fulfillment_url,
        )

        assert response.status_code == status.HTTP_200_OK
        self.learner_credit_course_enrollment.refresh_from_db()
        assert self.learner_credit_course_enrollment.is_revoked
        mock_enrollment_api.update_enrollment.assert_called_once()
        assert mock_enrollment_api.update_enrollment.call_args.args == (
            self.enterprise_course_enrollment.enterprise_customer_user.user.username,
            self.enterprise_course_enrollment.course_id,
        )
        assert mock_enrollment_api.update_enrollment.call_args.kwargs == {
            'is_active': False,
        }

    def test_cancel_fulfillment_nonexistent_enrollment(self):
        """
        Test that we get a 404 when trying to cancel a nonexistent enrollment.
        """
        response = self.client.post(
            settings.TEST_SERVER + reverse(
                'enterprise-subsidy-fulfillment',
                kwargs={'fulfillment_source_uuid': str(uuid.uuid4())}
            ) + '/cancel-fulfillment',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_fulfillment_belonging_to_different_enterprise(self):
        """
        Test that a non staff user cannot cancel a fulfillment belonging to a different enterprise.
        """
        self.user.is_staff = False
        other_enterprise_user = factories.EnterpriseCustomerUserFactory()
        other_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=other_enterprise_user
        )
        other_licensed_course_enrollment = factories.LicensedEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=other_enrollment,
        )
        response = self.client.post(
            settings.TEST_SERVER + reverse(
                'enterprise-subsidy-fulfillment',
                kwargs={'fulfillment_source_uuid': str(other_licensed_course_enrollment.uuid)}
            ) + '/cancel-fulfillment',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @mock.patch("enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api")
    def test_staff_can_cancel_fulfillments_not_belonging_to_them(self, mock_enrollment_api):
        """
        Test that a staff user can cancel a fulfillment belonging to a different enterprise.
        """
        self.user.is_staff = True
        self.user.save()
        mock_enrollment_api.update_enrollment.return_value = mock.Mock()
        other_enterprise_user = factories.EnterpriseCustomerUserFactory()
        other_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=other_enterprise_user
        )
        other_licensed_course_enrollment = factories.LicensedEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=other_enrollment,
        )
        response = self.client.post(
            settings.TEST_SERVER + reverse(
                'enterprise-subsidy-fulfillment',
                kwargs={'fulfillment_source_uuid': str(other_licensed_course_enrollment.uuid)}
            ) + '/cancel-fulfillment',
        )
        assert response.status_code == status.HTTP_200_OK


@ddt.ddt
@mark.django_db
class TestLicensedEnterpriseCourseEnrollmentViewset(BaseTestEnterpriseAPIViews):
    """
    Test LicensedEnterpriseCourseEnrollmentViewset
    """

    def test_validate_license_revoke_data_valid_data(self):
        request_data = {
            'user_id': 'anything',
            'enterprise_id': 'something',
        }
        # pylint: disable=protected-access
        self.assertIsNone(LicensedEnterpriseCourseEnrollmentViewSet._validate_license_revoke_data(request_data))

    @ddt.data(
        {},
        {'user_id': 'foo'},
        {'enterprise_id': 'bar'},
    )
    def test_validate_license_revoke_data_invalid_data(self, request_data):
        # pylint: disable=protected-access
        response = LicensedEnterpriseCourseEnrollmentViewSet._validate_license_revoke_data(request_data)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual('user_id and enterprise_id must be provided.', response.data)

    @ddt.data(
        CourseRunProgressStatuses.IN_PROGRESS,
        CourseRunProgressStatuses.UPCOMING,
        CourseRunProgressStatuses.COMPLETED,
        CourseRunProgressStatuses.SAVED_FOR_LATER,
    )
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_run_status')
    def test_revoke_has_user_completed_course_run(self, progress_status, mock_course_run_status, mock_cert_for_user):
        enrollment = mock.Mock()
        course_overview = {'id': 'some-course'}

        mock_course_run_status.return_value = progress_status
        expected_result = progress_status == CourseRunProgressStatuses.COMPLETED
        # pylint: disable=protected-access
        actual_result = LicensedEnterpriseCourseEnrollmentViewSet._has_user_completed_course_run(
            enrollment, course_overview
        )
        self.assertEqual(expected_result, actual_result)
        mock_cert_for_user.assert_called_once_with(
            enrollment.enterprise_customer_user.username, 'some-course'
        )
        mock_course_run_status.assert_called_once_with(
            course_overview, mock_cert_for_user.return_value, enrollment
        )

    def test_post_license_revoke_unplugged(self):
        post_data = {
            'user_id': 'bob',
            'enterprise_id': 'bobs-burgers',
        }
        with self.assertRaises(NotConnectedToOpenEdX):
            self.client.post(
                settings.TEST_SERVER + LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT,
                data=post_data,
            )

    def test_post_license_revoke_invalid_data(self):
        with mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api'):

            post_data = {
                'user_id': 'bob',
            }
            response = self.client.post(
                settings.TEST_SERVER + LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT,
                data=post_data,
            )
            self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_post_license_revoke_403(self):
        with mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews'), \
                mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api'):

            enterprise_customer = factories.EnterpriseCustomerFactory()
            self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(enterprise_customer.uuid))
            post_data = {
                'user_id': self.user.id,
                'enterprise_id': enterprise_customer.uuid,
            }
            response = self.client.post(
                settings.TEST_SERVER + LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT,
                data=post_data,
            )
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @ddt.data(
        {'is_course_completed': False, 'has_audit_mode': True},
        {'is_course_completed': True, 'has_audit_mode': True},
        {'is_course_completed': False, 'has_audit_mode': False},
        {'is_course_completed': True, 'has_audit_mode': False},
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_post_license_revoke_all_successes(
            self,
            mock_get_overviews,
            mock_get_certificate,
            mock_enrollment_api,
            mock_course_mode,
            is_course_completed,
            has_audit_mode,
    ):
        mock_course_mode.mode_for_course.return_value = has_audit_mode
        (
            enterprise_customer_user,
            enterprise_course_enrollment,
            licensed_course_enrollment,
        ) = self._revocation_factory_objects()

        mock_get_overviews_response = {
            'id': enterprise_course_enrollment.course_id,
            'pacing': 'instructor',
        }
        # update the mock response based on whether the course enrollment should be considered "completed"
        mock_get_overviews_response.update({
            'has_started': not is_course_completed,
            'has_ended': is_course_completed,
        })

        mock_get_overviews.return_value = [mock_get_overviews_response]
        mock_get_certificate.return_value = {'is_passing': False}
        mock_enrollment_api.return_value = mock.Mock(
            update_enrollment=mock.Mock(),
        )

        post_data = {
            'user_id': self.user.id,
            'enterprise_id': enterprise_customer_user.enterprise_customer.uuid,
        }
        response = self.client.post(
            settings.TEST_SERVER + LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT,
            data=post_data,
        )

        course_id = enterprise_course_enrollment.course_id
        expected_data = {
            course_id: {
                'success': True,
            },
        }
        EnrollmentTerminationStatus = LicensedEnterpriseCourseEnrollmentViewSet.EnrollmentTerminationStatus

        assert response.status_code == status.HTTP_200_OK
        if is_course_completed:
            expected_data[course_id]['message'] = EnrollmentTerminationStatus.COURSE_COMPLETED
        else:
            if has_audit_mode:
                expected_data[course_id]['message'] = EnrollmentTerminationStatus.MOVED_TO_AUDIT
            else:
                expected_data[course_id]['message'] = EnrollmentTerminationStatus.UNENROLLED
        self.assertEqual(expected_data, response.data)

        enterprise_course_enrollment.refresh_from_db()
        licensed_course_enrollment.refresh_from_db()

        # if the course was completed, the enrollment should not have been revoked,
        # and conversely, the enrollment should be revoked if the course was not completed
        revocation_expectation = not is_course_completed
        assert enterprise_course_enrollment.saved_for_later == revocation_expectation
        assert licensed_course_enrollment.is_revoked == revocation_expectation

        if not is_course_completed:
            if has_audit_mode:
                mock_enrollment_api.update_enrollment.assert_called_once_with(
                    username=enterprise_customer_user.username,
                    course_id=enterprise_course_enrollment.course_id,
                    mode=mock_course_mode.AUDIT,
                )
            else:
                mock_enrollment_api.update_enrollment.assert_called_once_with(
                    username=enterprise_customer_user.username,
                    course_id=enterprise_course_enrollment.course_id,
                    is_active=False,
                )

    @ddt.data(
        {'has_audit_mode': True},
        {'has_audit_mode': False}
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_post_license_revoke_all_errors(
            self,
            mock_get_overviews,
            mock_get_certificate,
            mock_enrollment_api,
            mock_course_mode,
            has_audit_mode,
    ):
        mock_course_mode.mode_for_course.return_value = has_audit_mode
        (
            enterprise_customer_user,
            enterprise_course_enrollment,
            licensed_course_enrollment,
        ) = self._revocation_factory_objects()

        mock_get_overviews_response = {
            'id': enterprise_course_enrollment.course_id,
            'pacing': 'instructor',
        }
        # update the mock response based on whether the course enrollment should be considered "completed"
        # this course is always not completed
        mock_get_overviews_response.update({
            'has_started': True,
            'has_ended': False,
        })

        mock_get_overviews.return_value = [mock_get_overviews_response]
        mock_get_certificate.return_value = {'is_passing': False}
        mock_enrollment_api.return_value = mock.Mock(
            update_enrollment=mock.Mock(),
        )

        mock_enrollment_api.update_enrollment.side_effect = Exception('Something went wrong')

        post_data = {
            'user_id': self.user.id,
            'enterprise_id': enterprise_customer_user.enterprise_customer.uuid,
        }
        response = self.client.post(
            settings.TEST_SERVER + LICENSED_ENTERPISE_COURSE_ENROLLMENTS_REVOKE_ENDPOINT,
            data=post_data,
        )

        course_id = enterprise_course_enrollment.course_id

        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        self.assertFalse(response.data[course_id]['success'])

        self.assertIn('Something went wrong', response.data[course_id]['message'])

        enterprise_course_enrollment.refresh_from_db()
        licensed_course_enrollment.refresh_from_db()

        self.assertFalse(enterprise_course_enrollment.saved_for_later)
        self.assertFalse(licensed_course_enrollment.is_revoked)

        if has_audit_mode:
            mock_enrollment_api.update_enrollment.assert_called_once_with(
                username=enterprise_customer_user.username,
                course_id=enterprise_course_enrollment.course_id,
                mode=mock_course_mode.AUDIT,
            )
        else:
            mock_enrollment_api.update_enrollment.assert_called_once_with(
                username=enterprise_customer_user.username,
                course_id=enterprise_course_enrollment.course_id,
                is_active=False
            )


@ddt.ddt
@mark.django_db
class TestBulkEnrollment(BaseTestEnterpriseAPIViews):
    """
    Test bulk enrollment (EnterpriseCustomerViewSet)
    """

    def _create_user_and_enterprise_customer(self, email, password):
        """
        Helper method to create the User and Enterprise Customer used in tests.
        """
        user = factories.UserFactory(email=email, is_active=True, is_staff=False)
        user.set_password(password)
        user.save()

        enterprise_customer = factories.EnterpriseCustomerFactory()
        enterprise_user = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer,
        )

        return user, enterprise_user, enterprise_customer

    def tearDown(self):
        """
        Clears the Django cache, which means that throttle limits
        will be reset between test runs.
        """
        super().tearDown()
        cache.clear()

    @ddt.data(
        # enrollment_info usage
        {
            'body': {
                'enrollments_info': [{
                    'email': 'abc@test.com',
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                }]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [{
                    'email': 'abc@test.com',
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'created': True,
                    'activation_link': None,
                }],
                'failures': []
            },
            'expected_num_pending_licenses': 1,
            'expected_events': [mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course')],
        },
        # Validation failure cases
        {
            'body': {},
            'expected_code': 400,
            'expected_response': {'non_field_errors': ['Must include the `enrollment_info` parameter in request.']},
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        {
            'body': {
                'licenses_info': {}
            },
            'expected_code': 400,
            'expected_response': {
                'licenses_info': {'non_field_errors': ['Expected a list of items but got type "dict".']}
            },
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        {
            'body': {
                'licenses_info': [{'email': 'abc@test.com', 'course_run_key': 'course-v1:edX+DemoX+Demo_Course'}]
            },
            'expected_code': 400,
            'expected_response': {
                'licenses_info': [
                    {
                        'non_field_errors': [
                            "At least one subsidy info field [license_uuid or transaction_id] required."
                        ],
                    }
                ]
            },
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        {
            'body': {
                'licenses_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': 'foobar',
                        'transaction_id': 'ayylmao'
                    },
                ]
            },
            'expected_code': 400,
            'expected_response': {
                'licenses_info': [
                    {
                        'non_field_errors': [
                            "Enrollment info contains conflicting subsidy information: "
                            "`license_uuid` and `transaction_id` found",
                        ]
                    }
                ]
            },
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        {
            'body': {
                'licenses_info': [
                    {
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    }
                ]
            },
            'expected_code': 400,
            'expected_response': {
                'licenses_info': [
                    {'non_field_errors': ['At least one user identifier field [user_id or email] required.']}
                ]
            },
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        {
            'body': {
                'licenses_info': [{
                    'email': 'BADLYFORMATTEDEMAIL',
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                }]
            },
            'expected_code': 409,
            'expected_response': {
                'successes': [], 'pending': [], 'failures': [], 'invalid_email_addresses': ['BADLYFORMATTEDEMAIL']
            },
            'expected_num_pending_licenses': 0,
            'expected_events': None,
        },
        # Single learner, single course success
        {
            'body': {
                'licenses_info': [{
                    'email': 'abc@test.com',
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                }]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [{
                    'email': 'abc@test.com',
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'created': True,
                    'activation_link': None,
                }],
                'failures': []
            },
            'expected_num_pending_licenses': 1,
            'expected_events': [mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course')],
        },
        # Multi-learner, single course success
        {
            'body': {
                'licenses_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                ]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    }
                ],
                'failures': []
            },
            'expected_num_pending_licenses': 2,
            'expected_events': [
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course'),
            ],
        },
        # Multi-learner, multi-course success
        {
            'body': {
                'licenses_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                ]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    }
                ],
                'failures': []
            },
            'expected_num_pending_licenses': 4,
            'expected_events': [
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course'),
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v2:edX+DemoX+Second_Demo_Course')
            ],
        },
        {
            'body': {
                'enrollments_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                ]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    }
                ],
                'failures': []
            },
            'expected_num_pending_licenses': 4,
            'expected_events': [
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course'),
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v2:edX+DemoX+Second_Demo_Course')
            ],
        },
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    @mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment')
    @mock.patch("enterprise.models.EnterpriseCustomer.notify_enrolled_learners")
    def test_bulk_enrollment_in_bulk_courses_pending_licenses(
        self,
        mock_notify_task,
        mock_track_enroll,
        mock_get_course_mode,
        body,
        expected_code,
        expected_response,
        expected_num_pending_licenses,
        expected_events,
    ):
        """
        Tests the bulk enrollment endpoint at enroll_learners_in_courses.
        This test currently does not create any users so is testing the pending
        enrollments case.
        """
        factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)
        mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

        self.assertEqual(len(PendingEnrollment.objects.all()), 0)
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT,
            data=json.dumps(body),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, expected_code)
        if expected_response:
            response_json = response.json()
            self.assertEqual(expected_response, response_json)
        self.assertEqual(len(PendingEnrollment.objects.all()), expected_num_pending_licenses)

        if expected_num_pending_licenses == 1:
            self.assertEqual(PendingEnrollment.objects.get().source.slug, EnterpriseEnrollmentSource.CUSTOMER_ADMIN)

        if expected_events:
            mock_track_enroll.assert_has_calls(expected_events[x] for x in range(len(expected_events) - 1))
        else:
            mock_track_enroll.assert_not_called()

        # no notifications to be sent unless 'notify' specifically asked for in payload
        mock_notify_task.assert_not_called()

    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    @mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment')
    @mock.patch('enterprise.models.EnterpriseCustomer.notify_enrolled_learners')
    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    @mock.patch('enterprise.utils.lms_enroll_user_in_course')
    @ddt.data(True, False)
    def test_bulk_enrollment_in_bulk_courses_existing_users(
        self,
        setting_value,
        mock_enroll_user_in_course,
        mock_update_or_create_enrollment,
        mock_notify_task,
        mock_track_enroll,
        mock_get_course_mode,
    ):
        """
        Tests the bulk enrollment endpoint at enroll_learners_in_courses.

        This tests the case where existing users are supplied, so the enrollments are fulfilled rather than pending.
        """
        if setting_value:
            mock_customer_admin_enroll_user = mock_update_or_create_enrollment
        else:
            mock_customer_admin_enroll_user = mock_enroll_user_in_course

        with override_settings(ENABLE_ENTERPRISE_BACKEND_EMET_AUTO_UPGRADE_ENROLLMENT_MODE=setting_value):
            mock_customer_admin_enroll_user.return_value = True

            user_one = factories.UserFactory(is_active=True)
            user_two = factories.UserFactory(is_active=True)

            factories.EnterpriseCustomerFactory(
                uuid=FAKE_UUIDS[0],
                name="test_enterprise"
            )

            permission = Permission.objects.get(name='Can add Enterprise Customer')
            self.user.user_permissions.add(permission)
            mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

            self.assertEqual(len(PendingEnrollment.objects.all()), 0)
            body = {
                'enrollments_info': [
                    {
                        'user_id': user_one.id,
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': user_two.email,
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                ]
            }
            response = self.client.post(
                settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT,
                data=json.dumps(body),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            response_json = response.json()
            self.assertEqual({
                'successes': [
                    {
                        'user_id': user_one.id,
                        'email': user_one.email,
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                        'enterprise_fulfillment_source_uuid': str(EnterpriseCourseEnrollment.objects.filter(
                            enterprise_customer_user__user_id=user_one.id
                        ).first().licensedenterprisecourseenrollment_enrollment_fulfillment.uuid)
                    },
                    {
                        'user_id': user_two.id,
                        'email': user_two.email,
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                        'enterprise_fulfillment_source_uuid': str(EnterpriseCourseEnrollment.objects.filter(
                            enterprise_customer_user__user_id=user_two.id
                        ).first().licensedenterprisecourseenrollment_enrollment_fulfillment.uuid)
                    },
                ],
                'pending': [],
                'failures': [],
            }, response_json)
            self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 2)
            # no notifications to be sent unless 'notify' specifically asked for in payload
            mock_notify_task.assert_not_called()
            mock_track_enroll.assert_has_calls([
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course'),
            ])
            if setting_value:
                assert mock_update_or_create_enrollment.call_count == 2
            else:
                assert mock_enroll_user_in_course.call_count == 2

    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    @mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment')
    @mock.patch('enterprise.models.EnterpriseCustomer.notify_enrolled_learners')
    def test_bulk_enrollment_in_bulk_courses_nonexisting_user_id(
        self,
        mock_notify_task,
        mock_track_enroll,
        mock_get_course_mode,
    ):
        """
        Tests the bulk enrollment endpoint at enroll_learners_in_courses.

        This tests the case where a non-existent user_id is supplied, so an error should occur.
        """
        user = factories.UserFactory(is_active=True)

        factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)
        mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

        self.assertEqual(len(PendingEnrollment.objects.all()), 0)
        body = {
            'enrollments_info': [
                {
                    'user_id': 9998,
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                },
                {
                    # Also make sure an invalid user_id fails even when a valid email is supplied.
                    'user_id': 9999,
                    'email': user.email,
                    'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                },
            ]
        }
        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT,
            data=json.dumps(body),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        response_json = response.json()
        self.assertEqual({
            'successes': [],
            'pending': [],
            'failures': [],
            'invalid_user_ids': [9998, 9999],
        }, response_json)

        mock_track_enroll.assert_not_called()

        # no notifications to be sent unless 'notify' specifically asked for in payload
        mock_notify_task.assert_not_called()

    @ddt.data(
        {
            'old_transaction_id': FAKE_UUIDS[4],
            'new_transaction_id': FAKE_UUIDS[4],
            'setting_value': True,
        },
        {
            'old_transaction_id': str(uuid.uuid4()),
            'new_transaction_id': str(uuid.uuid4()),
            'setting_value': False,
        },
    )
    @ddt.unpack
    @mock.patch("enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api")
    @mock.patch(
        'enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key'
    )
    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    @mock.patch('enterprise.utils.lms_enroll_user_in_course')
    def test_bulk_enrollment_enroll_after_cancel(
        self,
        mock_platform_enrollment,
        mock_get_course_mode,
        mock_update_or_create_enrollment,
        mock_enroll_user_in_course,
        old_transaction_id,
        new_transaction_id,
        setting_value,
    ):
        """
        Test that even after a cancelled enterprise enrollment, an attempt to re-enroll the same learner in content
        results in expected state and payload.
        """
        if setting_value:
            mock_enrollment_api = mock_update_or_create_enrollment
        else:
            mock_enrollment_api = mock_enroll_user_in_course
        with override_settings(ENABLE_ENTERPRISE_BACKEND_EMET_AUTO_UPGRADE_ENROLLMENT_MODE=setting_value):
            mock_platform_enrollment.return_value = True
            mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE
            # Needed for the cancel endpoint:
            mock_enrollment_api.update_enrollment.return_value = mock.Mock()

            user, enterprise_user, enterprise_customer = \
                self._create_user_and_enterprise_customer('abc@test.com', 'test_password')
            permission = Permission.objects.get(name='Can add Enterprise Customer')
            user.user_permissions.add(permission)

            course_id = 'course-v1:edX+DemoX+Demo_Course'
            enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
                enterprise_customer_user=enterprise_user,
                course_id=course_id,
            )
            learner_credit_course_enrollment = factories.LearnerCreditEnterpriseCourseEnrollmentFactory(
                enterprise_course_enrollment=enterprise_course_enrollment,
                transaction_id=old_transaction_id,
            )
            learner_credit_fulfillment_url = reverse(
                'enterprise-subsidy-fulfillment',
                kwargs={'fulfillment_source_uuid': str(learner_credit_course_enrollment.uuid)}
            )
            cancel_url = learner_credit_fulfillment_url + '/cancel-fulfillment'
            enrollment_url = reverse(
                'enterprise-customer-enroll-learners-in-courses',
                (str(enterprise_customer.uuid),)
            )
            enroll_body = {
                'notify': 'true',
                'enrollments_info': [
                    {
                        'email': user.email,
                        'course_run_key': course_id,
                        'transaction_id': new_transaction_id,
                    },
                ]
            }
            with mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment'):
                with mock.patch("enterprise.models.EnterpriseCustomer.notify_enrolled_learners"):
                    cancel_response = self.client.post(settings.TEST_SERVER + cancel_url)
                    with LogCapture(level=logging.WARNING) as warn_logs:
                        second_enroll_response = self.client.post(
                            settings.TEST_SERVER + enrollment_url,
                            data=json.dumps(enroll_body),
                            content_type='application/json',
                        )

            assert cancel_response.status_code == status.HTTP_200_OK
            assert second_enroll_response.status_code == status.HTTP_201_CREATED

            if old_transaction_id == new_transaction_id:
                assert any(
                    'using the same transaction_id as before'
                    in log_record.getMessage() for log_record in warn_logs.records
                )

            # First, check that the bulk enrollment response looks good:
            response_json = second_enroll_response.json()
            assert len(response_json.get('successes')) == 1
            assert response_json['successes'][0]['user_id'] == user.id
            assert response_json['successes'][0]['email'] == user.email
            assert response_json['successes'][0]['course_run_key'] == course_id
            assert response_json['successes'][0]['created'] is True
            assert uuid.UUID(response_json['successes'][0]['enterprise_fulfillment_source_uuid']) == \
                learner_credit_course_enrollment.uuid

            # Then, check that the db records related to the enrollment look good:
            enterprise_course_enrollment.refresh_from_db()
            learner_credit_course_enrollment.refresh_from_db()
            assert enterprise_course_enrollment.unenrolled_at is None
            assert enterprise_course_enrollment.saved_for_later is False
            assert learner_credit_course_enrollment.is_revoked is False
            assert learner_credit_course_enrollment.transaction_id == uuid.UUID(new_transaction_id)

    @ddt.data(
        {
            'body': {
                'notify': 'true',
                'enrollments_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'transaction_id': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                ]
            },
            'fulfillment_source': LearnerCreditEnterpriseCourseEnrollment,
            'setting_value': True,
        },
        {
            'body': {
                'notify': 'true',
                'enrollments_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                ]
            },
            'fulfillment_source': LicensedEnterpriseCourseEnrollment,
            'setting_value': False,
        },
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    @mock.patch('enterprise.utils.lms_enroll_user_in_course')
    def test_bulk_enrollment_includes_fulfillment_source_uuid(
        self,
        mock_get_course_mode,
        mock_update_or_create_enrollment,
        mock_enroll_user_in_course,
        setting_value,
        body,
        fulfillment_source,
    ):
        """
        Test that a successful bulk enrollmnet call to generate subsidy based enrollment records will return the newly
        generated subsidized enrollment uuid value as part of the response payload.
        """
        if setting_value:
            mock_platform_enrollment = mock_update_or_create_enrollment
        else:
            mock_platform_enrollment = mock_enroll_user_in_course
        with override_settings(ENABLE_ENTERPRISE_BACKEND_EMET_AUTO_UPGRADE_ENROLLMENT_MODE=setting_value):
            mock_platform_enrollment.return_value = True

            user, _, enterprise_customer = self._create_user_and_enterprise_customer(
                body.get('enrollments_info')[0].get('email'), 'test_password'
            )

            permission = Permission.objects.get(name='Can add Enterprise Customer')
            user.user_permissions.add(permission)
            mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

            enrollment_url = reverse(
                'enterprise-customer-enroll-learners-in-courses',
                (str(enterprise_customer.uuid),)
            )
            with mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment'):
                with mock.patch("enterprise.models.EnterpriseCustomer.notify_enrolled_learners"):
                    response = self.client.post(
                        settings.TEST_SERVER + enrollment_url,
                        data=json.dumps(body),
                        content_type='application/json',
                    )

            self.assertEqual(response.status_code, 201)

            response_json = response.json()
            self.assertEqual(len(response_json.get('successes')), 1)
            self.assertEqual(
                str(fulfillment_source.objects.first().uuid),
                response_json.get('successes')[0].get('enterprise_fulfillment_source_uuid')
            )

    @ddt.data(
        {
            'body': {
                'notify': 'true',
                'licenses_info': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                    },
                ]
            },
            'expected_code': 202,
            'expected_response': {
                'successes': [],
                'pending': [
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'abc@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    },
                    {
                        'email': 'xyz@test.com',
                        'course_run_key': 'course-v2:edX+DemoX+Second_Demo_Course',
                        'created': True,
                        'activation_link': None,
                    }
                ],
                'failures': []
            },
            'expected_num_pending_licenses': 4,
            'expected_events': [
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v1:edX+DemoX+Demo_Course'),
                mock.call(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, 1, 'course-v2:edX+DemoX+Second_Demo_Course')
            ],
        },
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    @mock.patch('enterprise.api.v1.views.enterprise_customer.track_enrollment')
    @mock.patch("enterprise.models.EnterpriseCustomer.notify_enrolled_learners")
    def test_bulk_enrollment_with_notification(
        self,
        mock_notify_task,
        mock_track_enroll,
        mock_get_course_mode,
        body,
        expected_code,
        expected_response,
        expected_num_pending_licenses,
        expected_events,
    ):
        """
        Tests the bulk enrollment endpoint at enroll_learners_in_courses.
        Explicitly checks that notification is invoked precisely once per course,
        with the associated learners included
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)
        mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

        self.assertEqual(len(PendingEnrollment.objects.all()), 0)

        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT,
            data=json.dumps(body),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, expected_code)

        response_json = response.json()
        self.assertEqual(expected_response, response_json)
        self.assertEqual(len(PendingEnrollment.objects.all()), expected_num_pending_licenses)

        mock_track_enroll.assert_has_calls(expected_events[x] for x in range(len(expected_events) - 1))

        # verify notification sent correctly for each course to applicable learners
        unique_course_keys = {item['course_run_key'] for item in body['licenses_info']}
        unique_learners = {item['email'] for item in body['licenses_info']}
        unique_ent_customer_users = set()
        for learner in unique_learners:
            try:
                # alternative was to have a factory that uses django_get_or_create
                # but did not want to change the existing factory or create a new one
                unique_ent_customer_users.add(
                    PendingEnterpriseCustomerUser.objects.get(user_email=learner)
                )
            except PendingEnterpriseCustomerUser.DoesNotExist:
                unique_ent_customer_users.add(PendingEnterpriseCustomerUserFactory(
                    enterprise_customer=enterprise_customer,
                    user_email=learner
                ))
        request_user = self.user

        def _make_call(course_run, enrolled_learners):
            return mock.call(
                catalog_api_user=request_user,
                course_id=course_run,
                users=enrolled_learners,
                admin_enrollment=True,
                activation_links={},
            )
        mock_calls = [_make_call(course_run, unique_ent_customer_users) for course_run in unique_course_keys]

        mock_notify_task.assert_has_calls(mock_calls, any_order=True)

    @mock.patch('enterprise.api.v1.views.enterprise_customer.enroll_subsidy_users_in_courses')
    @mock.patch('enterprise.api.v1.views.enterprise_customer.get_best_mode_from_course_key')
    def test_enroll_learners_in_courses_partial_failure(self, mock_get_course_mode, mock_enroll_user):
        """
        Tests that bulk users bulk enrollment endpoint properly handles partial failures.
        """
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )

        permission = Permission.objects.get(name='Can add Enterprise Customer')
        self.user.user_permissions.add(permission)

        pending_ecu, __ = PendingEnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=ent_customer,
            user_email='abc@test.com'
        )

        permanently_unlinked_user = UserFactory(email='unlinked@email.com')
        permanently_unlinked_ecu = EnterpriseCustomerUserFactory(
            enterprise_customer=ent_customer,
            user_id=permanently_unlinked_user.id,
            active=False,
            linked=False,
            is_relinkable=False
        )

        course = 'course-v1:edX+DemoX+Demo_Course'
        enrollment_response = {
            'pending': [{'email': 'abc@test.com', 'course_run_key': course, 'user': pending_ecu, 'created': True}],
            'successes': [],
            'failures': [{'email': 'xyz@test.com', 'course_run_key': course}]
        }
        mock_enroll_user.return_value = enrollment_response
        mock_get_course_mode.return_value = VERIFIED_SUBSCRIPTION_COURSE_MODE

        body = {
            'licenses_info': [
                {
                    'email': 'abc@test.com',
                    'course_run_key': course,
                    'license_uuid': '5a88bdcade7c4ecb838f8111b68e18ac'
                },
                {
                    'email': 'xyz@test.com',
                    'course_run_key': course,
                    'license_uuid': '2c58acdade7c4ede838f7111b42e18ac'
                },
                {
                    'email': permanently_unlinked_ecu.user.email,
                    'course_run_key': course,
                    'license_uuid': '3d58acdede7c2ede838f7111b42e18ac'
                }
            ]
        }

        response = self.client.post(
            settings.TEST_SERVER + ENTERPRISE_CUSTOMER_BULK_ENROLL_LEARNERS_IN_COURSES_ENDPOINT,
            data=json.dumps(body),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json(), enrollment_response)


@ddt.ddt
@mark.django_db
class TestExpiredLicenseCourseEnrollment(BaseTestEnterpriseAPIViews):
    """
    Test expired license course enrollment
    """

    def test_unenroll_expired_licensed_enrollments_unplugged(self):
        post_data = {
            'expired_license_uuids': ['uuid']
        }
        with self.assertRaises(NotConnectedToOpenEdX):
            self.client.post(
                settings.TEST_SERVER + EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT,
                data=post_data,
            )

    @ddt.data(
        {'is_course_completed': False, 'has_audit_mode': True},
        {'is_course_completed': True, 'has_audit_mode': True},
        {'is_course_completed': False, 'has_audit_mode': False},
        {'is_course_completed': True, 'has_audit_mode': False},
    )
    @ddt.unpack
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseEnrollment')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_unenroll_expired_licensed_enrollments(
            self,
            mock_get_overviews,
            mock_enrollment_api,
            mock_cert_for_user,
            mock_course_mode,
            _,
            is_course_completed,
            has_audit_mode,
    ):
        (
            enterprise_customer_user,
            enterprise_course_enrollment,
            licensed_course_enrollment,
        ) = self._revocation_factory_objects()
        expired_license_uuid = licensed_course_enrollment.license_uuid

        mock_course_mode.mode_for_course.return_value = has_audit_mode
        mock_get_overviews.return_value = [{
            'id': enterprise_course_enrollment.course_id,
            'pacing': 'instructor',
            'has_started': not is_course_completed,
            'has_ended': is_course_completed,
        }]
        mock_cert_for_user.return_value = {'is_passing': False}
        mock_enrollment_api.return_value = mock.Mock(
            update_enrollment=mock.Mock(),
        )

        post_data = {
            'expired_license_uuids': [str(expired_license_uuid), uuid.uuid4()]
        }
        self.client.post(
            settings.TEST_SERVER + EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT,
            data=post_data,
            format='json',
        )

        licensed_course_enrollment.refresh_from_db()
        enterprise_course_enrollment.refresh_from_db()

        if not is_course_completed:
            if has_audit_mode:
                mock_enrollment_api.update_enrollment.assert_called_once_with(
                    username=enterprise_customer_user.username,
                    course_id=enterprise_course_enrollment.course_id,
                    mode=mock_course_mode.AUDIT,
                )
            else:
                mock_enrollment_api.update_enrollment.assert_called_once_with(
                    username=enterprise_customer_user.username,
                    course_id=enterprise_course_enrollment.course_id,
                    is_active=False
                )
            assert licensed_course_enrollment.is_revoked
            assert enterprise_course_enrollment.saved_for_later
        else:
            assert not enterprise_course_enrollment.saved_for_later
            assert not licensed_course_enrollment.is_revoked

    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseEnrollment')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_unenroll_expired_licensed_enrollments_no_license_ids(
            self,
            *_
    ):
        post_data = {
            'user_id': self.user.id,
            'expired_license_uuids': []
        }
        response = self.client.post(
            settings.TEST_SERVER + EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT,
            data=post_data,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseEnrollment')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_unenroll_expired_licensed_enrollments_ignore_enrollments_modified_after(
            self,
            mock_get_overviews,
            mock_enrollment_api,
            mock_cert_for_user,
            mock_course_mode,
            mock_course_enrollment
    ):
        (
            enterprise_customer_user,
            enterprise_course_enrollment,
            licensed_course_enrollment,
        ) = self._revocation_factory_objects()

        mock_course_mode.mode_for_course.return_value = True
        mock_get_overviews.return_value = [{
            'id': enterprise_course_enrollment.course_id,
            'pacing': 'instructor',
            'has_started': True,
            'has_ended': False,
        }]
        mock_cert_for_user.return_value = {'is_passing': False}
        mock_enrollment_api.return_value = mock.Mock(
            update_enrollment=mock.Mock(),
        )
        expired_license_uuid = licensed_course_enrollment.license_uuid

        mock_course_enrollment.history.filter.return_value = mock.Mock(
            order_by=mock.Mock(return_value=[
                mock.Mock(
                    user_id=enterprise_customer_user.user_id,
                    course_id=enterprise_course_enrollment.course_id,
                    history_date=self.now
                )
            ])
        )

        post_data = {
            'expired_license_uuids': [str(expired_license_uuid)],
            'ignore_enrollments_modified_after': (self.now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
        self.client.post(
            settings.TEST_SERVER + EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT,
            data=post_data,
            format='json',
        )

        licensed_course_enrollment.refresh_from_db()
        enterprise_course_enrollment.refresh_from_db()

        assert not enterprise_course_enrollment.saved_for_later
        assert not licensed_course_enrollment.is_revoked
        assert mock_enrollment_api.update_enrollment.call_count == 0

    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseEnrollment')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.CourseMode')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_certificate_for_user')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.enrollment_api')
    @mock.patch('enterprise.api.v1.views.enterprise_subsidy_fulfillment.get_course_overviews')
    def test_unenroll_expired_licensed_enrollments_bad_ignore_enrollments_modified_after(
            self,
            *_
    ):
        post_data = {
            'user_id': self.user.id,
            'expired_license_uuids': [uuid.uuid4()],
            'ignore_enrollments_modified_after': 'bogus'
        }
        response = self.client.post(
            settings.TEST_SERVER + EXPIRED_LICENSED_ENTERPRISE_COURSE_ENROLLMENTS_ENDPOINT,
            data=post_data,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@ddt.ddt
@mark.django_db
class TestEnterpriseReportingConfigAPIViews(APITest):
    """
    Test Reporting Configuration Views
    """

    def _create_user_and_enterprise_customer(self, username, password):
        """
        Helper method to create the User and Enterprise Customer used in tests.
        """
        user = factories.UserFactory(username=username, is_active=True, is_staff=False)
        user.set_password(password)
        user.save()

        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer,
        )

        return user, enterprise_customer

    def _add_feature_role(self, user, feature_role):
        """
        Helper method to create a feature_role and connect it to the User
        """
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(
            name=feature_role
        )
        EnterpriseFeatureUserRoleAssignment.objects.create(user=user, role=feature_role_object)

    def _assert_config_response(self, expected_data, response_content):
        """
        Helper method to test the response data against the expected JSON data.
        """
        response_content.pop('enterprise_customer')
        for key, value in expected_data.items():
            assert response_content[key] == value

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_reporting_config_retrieve_permissions(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the retrieve endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'active': True,
            'delivery_method': 'email',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        expected_data = {
            'active': True,
            'delivery_method': 'email',
            'frequency': 'monthly',
            'email': ['test@test.com', 'foo@test.com'],
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        test_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.get(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(test_config.uuid)}
                ),
            )
        )

        assert response.status_code == expected_status
        if has_feature_role:
            response_content = self.load_json(response.content)
            assert response_content['enterprise_customer']['uuid'] == str(enterprise_customer.uuid)
            self._assert_config_response(expected_data, response_content)

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_reporting_config_list_permissions(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the retrieve endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'active': True,
            'delivery_method': 'email',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        expected_data = {
            'active': True,
            'delivery_method': 'email',
            'frequency': 'monthly',
            'email': ['test@test.com', 'foo@test.com'],
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        factories.EnterpriseCustomerReportingConfigFactory.create_batch(5, **model_item)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.get(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            )
        )

        assert response.status_code == expected_status
        if has_feature_role:
            results = self.load_json(response.content)['results']
            assert len(results) == 5
            response_content = results[0]
            assert response_content['enterprise_customer']['uuid'] == str(enterprise_customer.uuid)
            self._assert_config_response(expected_data, response_content)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_post_requires_enterprise_customer_id(self, request_or_stub_mock):
        """
        Verify that the POST endpoint requires enterprise_customer_id.
        """
        user, __ = self._create_user_and_enterprise_customer('test_user', 'test_password')

        post_data = {
            'active': 'true',
            'enable_compression': True,
            'delivery_method': 'email',
            'email': ['test@test.com', 'foo@test.com'],
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': ''
        }
        expected_data = post_data.copy()
        expected_data.update({
            'active': True,
            'encrypted_sftp_password': None,
        })
        expected_data.pop('encrypted_password')
        client = APIClient()
        client.login(username='test_user', password='test_password')

        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'enterprise_customer_id': ['This field is required.']}

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_201_CREATED),
    )
    @ddt.unpack
    def test_reporting_config_post_permissions(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the POST endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        post_data = {
            'active': 'true',
            'enable_compression': True,
            'delivery_method': 'email',
            'email': ['test@test.com', 'foo@test.com'],
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': ''
        }
        expected_data = post_data.copy()
        expected_data.update({
            'active': True,
            'encrypted_sftp_password': None,
        })
        expected_data.pop('encrypted_password')
        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        post_data.update({'enterprise_customer_id': enterprise_customer.uuid})
        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )

        assert response.status_code == expected_status
        if has_feature_role:
            response_content = self.load_json(response.content)
            assert response_content['enterprise_customer']['uuid'] == str(enterprise_customer.uuid)
            assert response_content['encrypted_password'] != post_data['encrypted_password']
            response_content.pop('encrypted_password')
            self._assert_config_response(expected_data, response_content)

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_reporting_config_put_permissions(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the PUT endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'active': True,
            'enable_compression': True,
            'delivery_method': 'email',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        put_data = {
            'enterprise_customer_id': str(enterprise_customer.uuid),
            'active': 'true',
            'enable_compression': True,
            'delivery_method': 'email',
            'email': ['test@test.com', 'foo@test.com'],
            'encrypted_password': 'passwordUpdate',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'json',
            'pgp_encryption_key': ''
        }
        expected_data = put_data.copy()
        expected_data.pop('encrypted_password')
        expected_data.update({
            'active': True,
        })
        expected_data.pop('enterprise_customer_id')
        test_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.put(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(test_config.uuid)}
                ),
            ),
            data=put_data,
            format='json',
        )

        assert response.status_code == expected_status
        if has_feature_role:
            response_content = self.load_json(response.content)
            assert response_content['enterprise_customer']['uuid'] == str(enterprise_customer.uuid)
            response_content.pop('enterprise_customer')
            assert response_content['encrypted_password'] is not None
            response_content.pop('encrypted_password')
            for key, value in expected_data.items():
                assert response_content[key] == value

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_validate_delivery_method(self, request_or_stub_mock):
        """
        Tests that the PUT endpoint raise error if delivery method is changed while report updation.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'active': True,
            'enable_compression': True,
            'delivery_method': 'email',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        put_data = {
            'enterprise_customer_id': str(enterprise_customer.uuid),
            'active': 'true',
            'enable_compression': True,
            'delivery_method': 'sftp',
            'email': [],
            'encrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'sftp_host_name',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'sft-_file_path',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': ''
        }

        test_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        put_data.update({
            'uuid': str(test_config.uuid),
        })

        client = APIClient()
        client.login(username='test_user', password='test_password')
        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        response = client.put(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(test_config.uuid)}
                ),
            ),
            data=put_data,
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assertEqual(
            response.json().get('delivery_method')[0],
            'Delivery method cannot be updated'
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_reporting_config_patch_permissions(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the PATCH endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'active': True,
            'enable_compression': True,
            'delivery_method': 'email',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        patch_data = {
            'enterprise_customer_id': str(enterprise_customer.uuid),
            'day_of_month': 4,
            'day_of_week': 1,
            'hour_of_day': 12,
            'enable_compression': True,
        }
        expected_data = patch_data.copy()
        expected_data.pop('enterprise_customer_id')
        patch_data['encrypted_password'] = 'newPassword'
        patch_data['encrypted_sftp_password'] = 'newSFTPPassword'

        test_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.patch(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(test_config.uuid)}
                ),
            ),
            data=patch_data,
            format='json',
        )

        assert response.status_code == expected_status
        if has_feature_role:
            response_content = self.load_json(response.content)
            assert response_content['enterprise_customer']['uuid'] == str(enterprise_customer.uuid)
            self._assert_config_response(expected_data, response_content)

    @ddt.data(
        {
            'email': None,
            'error': {'email': ['This field is required']},
            'status_code': status.HTTP_400_BAD_REQUEST
        },
        {
            'email': [],
            'error': {'email': ['This field is required']},
            'status_code': status.HTTP_400_BAD_REQUEST
        },
        {
            'email': ['xyz'],
            'error': {'email': {'0': ['Enter a valid email address.']}},
            'status_code': status.HTTP_400_BAD_REQUEST
        }
    )
    @ddt.unpack
    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_email_delivery(self, request_mock, email, error, status_code):
        """
        Tests that the POST endpoint raises error for email delivery type reporting config with incorrect email field.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        post_data = {
            'active': 'true',
            'enable_compression': 'true',
            'delivery_method': 'email',
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': '',
        }
        if email is not None:
            post_data['email'] = email

        client = APIClient()
        client.login(username='test_user', password='test_password')
        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        post_data.update({'enterprise_customer_id': enterprise_customer.uuid})
        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )

        assert response.status_code == status_code
        if error:
            assert response.json() == error

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_sftp_delivery(self, request_mock):
        """
        Tests that the POST endpoint works as expected for sftp delivery type reporting config without email field.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        post_data = {
            'active': 'true',
            'enable_compression': 'true',
            'delivery_method': 'sftp',
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': ''
        }

        client = APIClient()
        client.login(username='test_user', password='test_password')
        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        post_data.update({'enterprise_customer_id': enterprise_customer.uuid})
        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_patch_with_email_delivery(self, request_or_stub_mock):
        """
        Tests that the PATCH endpoint respects the Feature Role permissions assigned.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'active': True,
            'enable_compression': True,
            'delivery_method': 'email',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }
        patch_data = {
            'enterprise_customer_id': str(enterprise_customer.uuid),
            'email': [],
        }

        test_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        client = APIClient()
        client.login(username='test_user', password='test_password')

        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        response = client.patch(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(test_config.uuid)}
                ),
            ),
            data=patch_data,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_enterprise_catalogs_error(self, request_mock):
        """
        Tests that the POST endpoint raises error if enterprise catalogs are not associated with the given enterprise.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        # Create a new enterprise customer catalog that is not associated with above enterprise customer.
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory()

        post_data = {
            'active': 'true',
            'enable_compression': 'true',
            'delivery_method': 'email',
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': '',
            'email': ['test.email@example.com'],
            'enterprise_customer_catalog_uuids': [enterprise_catalog.uuid]
        }
        client = APIClient()
        client.login(username='test_user', password='test_password')
        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        post_data.update({'enterprise_customer_id': enterprise_customer.uuid})
        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )
        error = {
            'enterprise_customer_catalog_uuids': [
                'Only those catalogs can be linked that belong to the enterprise customer.',
            ]
        }
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == error

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_enterprise_catalogs_create(self, request_mock):
        """
        Tests that the POST endpoint links enterprise customer catalogs with the newly created reporting config.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        # Create a new enterprise customer catalog that is associated with above enterprise customer.
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)

        post_data = {
            'active': 'true',
            'enable_compression': 'true',
            'delivery_method': 'email',
            'encrypted_password': 'testPassword',
            'frequency': 'monthly',
            'day_of_month': 1,
            'day_of_week': 3,
            'hour_of_day': 1,
            'sftp_hostname': 'null',
            'sftp_port': 22,
            'sftp_username': 'test@test.com',
            'sftp_file_path': 'null',
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'pgp_encryption_key': '',
            'email': ['test.email@example.com'],
            'enterprise_customer_catalog_uuids': [enterprise_catalog.uuid]
        }
        client = APIClient()
        client.login(username='test_user', password='test_password')
        self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)
        request_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=ENTERPRISE_ADMIN_ROLE)

        post_data.update({'enterprise_customer_id': enterprise_customer.uuid})
        response = client.post(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-list'
                ),
            ),
            data=post_data,
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        ec_catalog_uuids = [item['uuid'] for item in response.json()['enterprise_customer_catalogs']]

        # Make sure the enterprise customer catalog was linked with the reporting configuration.
        assert [str(enterprise_catalog.uuid)] == ec_catalog_uuids

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_reporting_config_enterprise_catalogs_update(self, request_or_stub_mock):
        """
        Tests that the POST endpoint updates enterprise customer catalogs along with the reporting config.
        """
        has_feature_role = True
        expected_status = status.HTTP_200_OK

        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        model_item = {
            'active': True,
            'enable_compression': True,
            'delivery_method': 'email',
            'day_of_month': 1,
            'day_of_week': None,
            'hour_of_day': 1,
            'enterprise_customer': enterprise_customer,
            'email': 'test@test.com\nfoo@test.com',
            'decrypted_password': 'test_password',
            'decrypted_sftp_password': 'test_password',
            'frequency': 'monthly',
            'report_type': 'csv',
            'data_type': 'progress_v3',
        }

        reporting_config = factories.EnterpriseCustomerReportingConfigFactory.create(**model_item)

        # Create a new enterprise customer catalog that is associated with above enterprise customer
        # and also linked with the above reporting configuration.
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)
        reporting_config.enterprise_customer_catalogs.add(enterprise_catalog)
        reporting_config.save()

        # Create a  new enterprise customer catalog that is associated with above enterprise customer but not with
        # the above reporting configuration.
        enterprise_catalog_2 = factories.EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)

        patch_data = {
            'enterprise_customer_id': str(enterprise_customer.uuid),
            'day_of_month': 4,
            'enable_compression': True,
            'day_of_week': 1,
            'hour_of_day': 12,
            'enterprise_customer_catalog_uuids': [enterprise_catalog_2.uuid]
        }
        expected_data = patch_data.copy()
        expected_data.pop('enterprise_customer_id')
        patch_data['encrypted_password'] = 'newPassword'
        patch_data['encrypted_sftp_password'] = 'newSFTPPassword'

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)

        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.get(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(reporting_config.uuid)}
                ),
            ),
            format='json',
        )
        # validate the existing associated catalogs.
        print(response.content)
        assert response.status_code == status.HTTP_200_OK
        ec_catalog_uuids = [item['uuid'] for item in response.json()['enterprise_customer_catalogs']]
        assert [str(enterprise_catalog.uuid)] == ec_catalog_uuids

        response = client.patch(
            '{server}{reverse_url}'.format(
                server=settings.TEST_SERVER,
                reverse_url=reverse(
                    'enterprise-customer-reporting-detail',
                    kwargs={'uuid': str(reporting_config.uuid)}
                ),
            ),
            data=patch_data,
            format='json',
        )

        assert response.status_code == expected_status
        ec_catalog_uuids = [item['uuid'] for item in response.json()['enterprise_customer_catalogs']]

        # Make sure the enterprise customer catalog was linked with the reporting configuration.
        assert [str(enterprise_catalog_2.uuid)] == ec_catalog_uuids


class TestReadNotificationView(BaseTestEnterpriseAPIViews):
    """
    Test NotificationReadView
    """

    READ_NOTIFICATION_ENDPOINT = reverse('read-notification')

    def setUp(self):
        super().setUp()
        self.user, self.enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')
        self.admin_notification = factories.AdminNotificationFactory()
        self.client = APIClient()
        self.client.login(username='test_user', password='test_password')

        self._add_feature_role(self.user, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)

    def _create_user_and_enterprise_customer(self, username, password):
        """
        Helper method to create the User and Enterprise Customer used in tests.
        """
        user = factories.UserFactory(username=username, is_active=True, is_staff=False)
        user.set_password(password)
        user.save()

        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer,
        )

        return user, enterprise_customer

    def _add_feature_role(self, user, feature_role):
        """
        Helper method to create a feature_role and connect it to the User
        """
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(
            name=feature_role
        )
        EnterpriseFeatureUserRoleAssignment.objects.create(user=user, role=feature_role_object)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_read_notification_request_success(
            self,
            request_or_stub_mock,

    ):
        """
        Ensure request success status code.
        """
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)
        response = self.client.post(
            settings.TEST_SERVER + self.READ_NOTIFICATION_ENDPOINT,
            data={
                'notification_id': self.admin_notification.id,
                'enterprise_slug': self.enterprise_customer.slug
            }
        )
        assert response.status_code == 200

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_read_notification_request_error(
            self,
            request_or_stub_mock,

    ):
        """
        Ensure request fail status code for invalid param values.
        """
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)
        response = self.client.post(
            settings.TEST_SERVER + self.READ_NOTIFICATION_ENDPOINT,
            data={
                'notification_id': 111111,
                'enterprise_slug': 'random_slug'
            }
        )
        assert response.status_code == 500

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_read_notification_request_fail_missing_params(
            self,
            request_or_stub_mock,

    ):
        """
        Ensure request fail status code for missing params.
        """
        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)
        response = self.client.post(
            settings.TEST_SERVER + self.READ_NOTIFICATION_ENDPOINT,
            data={
                'notification_id': self.admin_notification.id,
            }
        )
        assert response.status_code == 400

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_read_notification_request_fail_non_admin_role(
            self,
            request_or_stub_mock,

    ):
        """
        Ensure request fail status code for non admin user.
        """
        system_wide_role = ''
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)
        response = self.client.post(
            settings.TEST_SERVER + self.READ_NOTIFICATION_ENDPOINT,
            data={
                'notification_id': self.admin_notification.id,
            }
        )
        assert response.status_code == 403


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerReportTypesView(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCustomerReportTypesView
    """

    REPORT_TYPES_ENDPOINT = 'enterprise-report-types'

    def _create_user_and_enterprise_customer(self, username, password):
        """
        Helper method to create the User and Enterprise Customer used in tests.
        """
        user = factories.UserFactory(username=username, is_active=True, is_staff=False)
        user.set_password(password)
        user.save()

        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer,
        )
        return user, enterprise_customer

    def _add_feature_role(self, user, feature_role):
        """
        Helper method to create a feature_role and connect it to the User
        """
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(
            name=feature_role
        )
        EnterpriseFeatureUserRoleAssignment.objects.create(user=user, role=feature_role_object)

    @ddt.data(
        (False, enterprise_report_choices.LIMITED_REPORT_TYPES),
        (True, enterprise_report_choices.FULL_REPORT_TYPES),
    )
    @ddt.unpack
    def test_get_enterprise_report_types(self, is_pearson, expected_report_choices):
        """
        Test that `EnterpriseCustomerReportTypesView` returns expected response.
        """
        enterprise_slug = 'pearson' if is_pearson else 'some-slug'
        enterprise_customer = factories.EnterpriseCustomerFactory(slug=enterprise_slug)
        expected_report_types = expected_report_choices

        response = self.client.get(
            settings.TEST_SERVER + reverse(
                self.REPORT_TYPES_ENDPOINT, kwargs={'enterprise_uuid': enterprise_customer.uuid}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected_report_types)

    def test_get_enterprise_not_found(self):
        """
        Test that `EnterpriseCustomerReportTypesView` returns correct response when enterprise is not found.
        """
        non_existed_id = 100
        response = self.client.get(
            settings.TEST_SERVER + reverse(
                self.REPORT_TYPES_ENDPOINT, kwargs={'enterprise_uuid': non_existed_id}
            )
        )
        self.assertEqual(response.status_code, 404)
        response = response.json()
        self.assertEqual(response['detail'], 'Could not find the enterprise customer.')

    def test_get_report_types_post_method_not_allowed(self):
        """
        Test that `EnterpriseCustomerReportTypesView` does not allow POST method.
        """
        response = self.client.post(
            settings.TEST_SERVER + reverse(self.REPORT_TYPES_ENDPOINT, kwargs={'enterprise_uuid': 1}),
            data=json.dumps({'some': 'postdata'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 405)
        response = response.json()
        self.assertEqual(response['detail'], 'Method "POST" not allowed.')

    def test_get_report_types_not_logged_in(self):
        """
        Test that `EnterpriseCustomerReportTypesView` only allows logged in users.
        """
        client = APIClient()
        # User is not logged in.
        response = client.get(
            settings.TEST_SERVER + reverse(self.REPORT_TYPES_ENDPOINT, kwargs={'enterprise_uuid': 1})
        )
        self.assertEqual(response.status_code, 401)
        response = response.json()
        self.assertEqual(response['detail'], 'Authentication credentials were not provided.')

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        (False, status.HTTP_403_FORBIDDEN),
        (True, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_auth_report_types_view(self, has_feature_role, expected_status, request_or_stub_mock):
        """
        Tests that the EnterpriseCustomerReportTypesView::get endpoint auth works as expected.
        """
        user, enterprise_customer = self._create_user_and_enterprise_customer('test_user', 'test_password')

        client = APIClient()
        client.login(username='test_user', password='test_password')

        if has_feature_role:
            self._add_feature_role(user, ENTERPRISE_DASHBOARD_ADMIN_ROLE)

        system_wide_role = ENTERPRISE_ADMIN_ROLE
        request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(system_wide_role=system_wide_role)

        response = client.get(
            '{server}{view_url}'.format(
                server=settings.TEST_SERVER,
                view_url=reverse(self.REPORT_TYPES_ENDPOINT, kwargs={'enterprise_uuid': enterprise_customer.uuid})
            ),
        )
        self.assertEqual(response.status_code, expected_status)


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerInviteKeyViewSet(BaseTestEnterpriseAPIViews):
    """
    Test EnterpriseCustomerInviteKeyViewSet
    """

    ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT = 'enterprise-customer-invite-key-detail'
    ENTERPRISE_CUSTOMER_INVITE_KEY_LIST_ENDPOINT = 'enterprise-customer-invite-key-list'
    ENTERPRISE_CUSTOMER_INVITE_KEY_BASIC_LIST_ENDPOINT = 'enterprise-customer-invite-key-basic-list'
    ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER = 'enterprise-customer-invite-key-link-user'
    USERNAME = "unlinkedtestuser"

    def setUp(self):
        super().setUp()
        enterprise_customer_1 = factories.EnterpriseCustomerFactory()
        enterprise_customer_2 = factories.EnterpriseCustomerFactory()
        enterprise_customer_1_invite_key = factories.EnterpriseCustomerInviteKeyFactory(
            enterprise_customer=enterprise_customer_1
        )
        self.enterprise_customer_1 = enterprise_customer_1
        self.enterprise_customer_2 = enterprise_customer_2
        self.enterprise_customer_1_invite_key = enterprise_customer_1_invite_key

        self.enterprise_customer_3 = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_3_invite_key = factories.EnterpriseCustomerInviteKeyFactory(
            enterprise_customer=self.enterprise_customer_3,
            expiration_date=localized_utcnow() + timedelta(days=365),
        )
        self.invalid_enterprise_customer_3_invite_key = factories.EnterpriseCustomerInviteKeyFactory(
            enterprise_customer=self.enterprise_customer_3,
            expiration_date=localized_utcnow() - timedelta(days=365),
        )

    def tearDown(self):
        super().tearDown()
        EnterpriseCustomer.objects.all().delete()
        EnterpriseCustomerInviteKey.objects.all().delete()

    def test_retrieve_allowed_for_authenticated_users(self):
        """
        Test that `EnterpriseCustomerInviteKeyViewSet` does not require roles for for getting an invite key.
        """
        response = self.client.get(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT,
                kwargs={'pk': str(self.enterprise_customer_1_invite_key.uuid)}
            )
        )
        self.assertEqual(response.status_code, 200)

    @ddt.data(True, False)
    def test_create_allowed_only_for_enterprise_admins(self, is_enterprise_admin):
        """
        Test that `EnterpriseCustomerInviteKeyViewSet` only allows enterprise admins to create invite keys.
        """
        context = str(self.enterprise_customer_1.uuid) if is_enterprise_admin else str(self.enterprise_customer_2.uuid)
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, context)

        future_date = datetime.utcnow() + timedelta(days=365)
        response = self.client.post(
            settings.TEST_SERVER + reverse(self.ENTERPRISE_CUSTOMER_INVITE_KEY_LIST_ENDPOINT),
            data=json.dumps(
                {
                    'enterprise_customer_uuid': str(self.enterprise_customer_1.uuid),
                    'expiration_date': future_date.isoformat()
                }
            ),
            content_type='application/json'
        )

        expected_status_code = 201 if is_enterprise_admin else 403
        self.assertEqual(response.status_code, expected_status_code)

    def test_put_method_not_allowed(self):
        """
        Test that `EnterpriseCustomerInviteKeyViewSet` does not allow PUT method.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(self.enterprise_customer_1.uuid))
        response = self.client.put(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT,
                kwargs={'pk': str(self.enterprise_customer_1_invite_key.uuid)}
            ),
            data=json.dumps({'some': 'putdata'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 405)
        response = response.json()
        self.assertEqual(response['detail'], 'Method "PUT" not allowed.')

    def test_patch_422_error(self):
        """
        Test that `EnterpriseCustomerInviteKeyViewSet` returns a 422 when trying to set is_active to True from False.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(self.enterprise_customer_1.uuid))
        self.enterprise_customer_1_invite_key.is_active = False
        self.enterprise_customer_1_invite_key.save()
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT,
                kwargs={'pk': str(self.enterprise_customer_1_invite_key.uuid)}
            ),
            data=json.dumps({'is_active': 'True'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 422)
        response = response.json()
        self.assertEqual(response['detail'], 'Cannot reactivate an inactive invite key.')

    def test_link_user_successful_link(self):
        """
        Test `{enterprise_customer_invite_key}/link-user` creates an `EnterpriseCustomerUser`
        """
        unlinked_user = factories.UserFactory(
            is_active=True,
            is_staff=False,
        )
        unlinked_user.set_password(TEST_PASSWORD)
        unlinked_user.save()

        client = APIClient()
        client.login(username=unlinked_user.username, password=TEST_PASSWORD)

        response = client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': self.enterprise_customer_3_invite_key.uuid}
            )
        )
        self.assertEqual(response.status_code, 201)
        assert EnterpriseCustomerUser.objects.get(
            user_id=unlinked_user.id,
            enterprise_customer=self.enterprise_customer_3,
            invite_key=self.enterprise_customer_3_invite_key,
        )
        response = self.load_json(response.content)
        assert response['enterprise_customer_slug'] == self.enterprise_customer_3.slug
        assert response['enterprise_customer_uuid'] == str(self.enterprise_customer_3.uuid)

    def test_enterprise_user_exists(self):
        """
        Test `{enterprise_customer_invite_key}/link-user` if one does not create `EnterpriseCustomerUser`
        If one already exists
        """
        unlinked_user = factories.UserFactory(
            is_active=True,
            is_staff=False,
        )
        unlinked_user.set_password(TEST_PASSWORD)
        unlinked_user.save()

        EnterpriseCustomerUser.objects.create(
            user_id=unlinked_user.id,
            enterprise_customer=self.enterprise_customer_3,
            active=False,
            linked=False,
        )

        client = APIClient()
        client.login(username=unlinked_user.username, password=TEST_PASSWORD)

        response_0 = client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': self.enterprise_customer_3_invite_key.uuid}
            )
        )
        self.assertEqual(response_0.status_code, 200)
        assert EnterpriseCustomerUser.objects.get(
            user_id=unlinked_user.id,
            enterprise_customer=self.enterprise_customer_3,
            active=True,
            linked=True,
        )
        json_0 = self.load_json(response_0.content)
        assert json_0['enterprise_customer_slug'] == self.enterprise_customer_3.slug
        assert json_0['enterprise_customer_uuid'] == str(self.enterprise_customer_3.uuid)

        response_1 = client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': self.enterprise_customer_3_invite_key.uuid}
            )
        )
        self.assertEqual(response_1.status_code, 200)
        json_1 = self.load_json(response_1.content)
        assert json_1['enterprise_customer_slug'] == self.enterprise_customer_3.slug
        assert json_1['enterprise_customer_uuid'] == str(self.enterprise_customer_3.uuid)

    def test_unlinkable_user_422(self):
        """
        Test 422 returned if user is not linked but is not relinkable.
        """
        unlinked_user = factories.UserFactory(
            is_active=True,
            is_staff=False,
        )
        unlinked_user.set_password(TEST_PASSWORD)

        unlinked_user.save()

        EnterpriseCustomerUser.objects.create(
            user_id=unlinked_user.id,
            enterprise_customer=self.enterprise_customer_3,
            active=False,
            linked=False,
            is_relinkable=False
        )

        client = APIClient()
        client.login(username=unlinked_user.username, password=TEST_PASSWORD)

        response = client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': self.enterprise_customer_3_invite_key.uuid}
            )
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_invalid_link(self):
        """
        Test that when an invalid link is used 422 is returned
        """
        response = self.client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': self.invalid_enterprise_customer_3_invite_key.uuid}
            )
        )
        self.assertEqual(response.status_code, 422)

    def test_no_link_found(self):
        """
        Test if `{enterprise_customer_invite_key}` does not exist, 400 is returned
        """
        response = self.client.post(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_ENDPOINT_LINK_USER,
                kwargs={'pk': str(uuid.uuid4())}
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_basic_list_no_pagination_200(self):
        """
        Test that basic-list endpoint returns unpaginated response.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(self.enterprise_customer_1.uuid))
        response = self.client.get(
            settings.TEST_SERVER + reverse(
                self.ENTERPRISE_CUSTOMER_INVITE_KEY_BASIC_LIST_ENDPOINT,
            )
        )
        self.assertEqual(response.status_code, 200)


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerToggleUniversalLinkView(BaseTestEnterpriseAPIViews):
    """
    Test toggle_universal_link in EnterpriseCustomerViewSet
    """
    TOGGLE_UNIVERSAL_LINK_ENDPOINT = 'enterprise-customer-toggle-universal-link'
    REQUEST_BODY_TRUE = json.dumps({'enable_universal_link': 'true'})
    REQUEST_BODY_FALSE = json.dumps({'enable_universal_link': 'false'})

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory(name="test_enterprise")
        self.user = factories.UserFactory(
            is_active=True,
            is_staff=False,
        )
        self.user.set_password(TEST_PASSWORD)
        self.user.save()

        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(name=ENTERPRISE_DASHBOARD_ADMIN_ROLE)
        EnterpriseFeatureUserRoleAssignment.objects.create(user=self.user, role=feature_role_object)
        self.client = APIClient()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)

    def tearDown(self):
        super().tearDown()
        EnterpriseCustomer.objects.all().delete()
        EnterpriseCustomerInviteKey.objects.all().delete()

    def test_permissions(self):
        """
        Tests permissions work as expected
        """

        non_admin_user = factories.UserFactory(
            is_active=True,
            is_staff=False,
        )
        non_admin_user.set_password(TEST_PASSWORD)
        non_admin_user.save()

        non_admin_client = APIClient()
        non_admin_client.login(username=non_admin_user.username, password=TEST_PASSWORD)

        forbidden_response = non_admin_client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            )
        )
        self.assertEqual(forbidden_response.status_code, 403)

        allowed_response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            ),
            data=self.REQUEST_BODY_TRUE,
            content_type='application/json',
        )
        self.assertEqual(allowed_response.status_code, 200)

    def test_toggle(self):
        # Toggle to True with date should create a link
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            ),
            data=json.dumps({
                'enable_universal_link': 'true',
                'expiration_date': str(datetime.utcnow())
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        assert EnterpriseCustomer.objects.get(
            uuid=self.enterprise_customer.uuid
        ).enable_universal_link

        assert EnterpriseCustomerInviteKey.objects.filter(
            enterprise_customer=self.enterprise_customer,
            is_active=True,
        ).count() == 1

        # Toggle to False should disable link
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            ),
            data=json.dumps({'enable_universal_link': 'false'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        assert not EnterpriseCustomer.objects.get(
            uuid=self.enterprise_customer.uuid
        ).enable_universal_link

        assert EnterpriseCustomerInviteKey.objects.filter(
            enterprise_customer=self.enterprise_customer,
            is_active=True,
        ).count() == 0

    def test_enterprise_user_not_found(self):
        """
        Test invalid uuid
        """
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                (str(uuid.uuid4()),),
            ),
            data=json.dumps({'enable_universal_link': 'true'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    @ddt.data(
        {'enable_universal_link': 'foo'},
        {'expiration_date': 'bar'},
        {'enable_universal_link': 'foo', 'expiration_date': 'bar'},
        {'enable_universal_link': 'foo', 'expiration_date': str(datetime.utcnow())},
        {'enable_universal_link': 'true', 'expiration_date': 'bar'},
    )
    def test_invalid_data(self, data):
        """
        Test invalid json data
        """
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            ),
            data=json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_same_enable_universal_link(self):
        """
        Test toggling to same value returns "No Changes" message
        """
        response = self.client.patch(
            settings.TEST_SERVER + reverse(
                self.TOGGLE_UNIVERSAL_LINK_ENDPOINT,
                kwargs={'pk': self.enterprise_customer.uuid}
            ),
            data=self.REQUEST_BODY_FALSE,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        response = response.json()
        self.assertEqual(response['detail'], 'No changes')


@mark.django_db
class TestPlotlyAuthView(APITest):
    """
    Test PlotlyAuthView
    """

    PLOTLY_TOKEN_ENDPOINT = 'plotly-token'

    def setUp(self):
        """
        Common setup for all tests.
        """
        super().setUp()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        self.enterprise_uuid = fake.uuid4()
        self.enterprise_uuid2 = fake.uuid4()
        self.url = settings.TEST_SERVER + reverse(
            self.PLOTLY_TOKEN_ENDPOINT, kwargs={'enterprise_uuid': self.enterprise_uuid}
        )

    def test_view_with_normal_user(self):
        """
        Verify that a user without having `enterprise.can_access_admin_dashboard` role can't access the view.
        """
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'Missing: enterprise.can_access_admin_dashboard'}

    def test_view_with_admin_user(self):
        """
        Verify that an enterprise admin user having `enterprise.can_access_admin_dashboard` role can access the view.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'token' in response.json()

    def test_view_with_admin_user_tries(self):
        """
        Verify that an enterprise admin can create token for enterprise uuid present in jwt roles only.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

        url = settings.TEST_SERVER + reverse(
            self.PLOTLY_TOKEN_ENDPOINT, kwargs={'enterprise_uuid': self.enterprise_uuid2}
        )

        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'Missing: enterprise.can_access_admin_dashboard'}


@mark.django_db
class TestAnalyticsSummaryView(APITest):
    """
    Test AnalyticsSummaryView
    """

    ANALYTICS_SUMMARY_ENDPOINT = 'analytics-summary'

    def setUp(self):
        """
        Common setup for all tests.
        """
        super().setUp()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        self.enterprise_uuid = fake.uuid4()
        self.enterprise_uuid2 = fake.uuid4()
        self.url = settings.TEST_SERVER + reverse(
            self.ANALYTICS_SUMMARY_ENDPOINT, kwargs={'enterprise_uuid': self.enterprise_uuid}
        )

        self.learner_progress = {
            'enterprise_customer_uuid': '288e94c6-2565-4e8d-a7f2-57df437d6052',
            'enterprise_customer_name': 'test enterprise',
            'active_subscription_plan': True,
            'assigned_licenses': 10,
            'activated_licenses': 5,
            'assigned_licenses_percentage': 0.6,
            'activated_licenses_percentage': 0.5,
            'active_enrollments': 4,
            'at_risk_enrollment_less_than_one_hour': 3,
            'at_risk_enrollment_end_date_soon': 2,
            'at_risk_enrollment_dormant': 2,
            'created_at': '2023-08-10T12:39:35.388936Z'
        }

        self.learner_engagement = {
            'enterprise_customer_uuid': '288e94c6-2565-4e8d-a7f2-57df437d6052',
            'enterprise_customer_name': 'test enterprise',
            'enrolls': 100,
            'enrolls_prior': 70,
            'passed': 30,
            'passed_prior': 50,
            'engage': 40,
            'engage_prior': 50,
            'hours': 2000,
            'hours_prior': 3000,
            'contract_end_date': '2023-12-10T12:39:28.792421Z',
            'active_contract': True,
            'created_at': '2023-08-11T13:25:40.197061Z'
        }

        self.payload = {
            'learner_progress': self.learner_progress,
            'learner_engagement': self.learner_engagement,
        }

    def test_view_with_normal_user(self):
        """
        Verify that a user without having `enterprise.can_access_admin_dashboard` role can't access the view.
        """
        response = self.client.post(self.url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'Missing: enterprise.can_access_admin_dashboard'}

    def test_view_with_admin_user_tries(self):
        """
        Verify that an enterprise admin can access this view only for itself.
        """
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

        url = settings.TEST_SERVER + reverse(
            self.ANALYTICS_SUMMARY_ENDPOINT, kwargs={'enterprise_uuid': self.enterprise_uuid2}
        )

        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        response = self.client.post(url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'Missing: enterprise.can_access_admin_dashboard'}

    @mock.patch('enterprise.models.chat_completion')
    def test_view_with_admin_user(self, mock_chat_completion):
        """
        Verify that an enterprise admin user having `enterprise.can_access_admin_dashboard` role can access the view.
        """
        mock_chat_completion.return_value = 'Test Response.'
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        EnterpriseCustomerFactory.create(uuid=self.enterprise_uuid)

        response = self.client.post(self.url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'learner_progress' in response.json()
        assert 'learner_engagement' in response.json()

    @mock.patch('enterprise.models.chat_completion')
    def test_404_if_enterprise_customer_does_not_exist(self, mock_chat_completion):
        """
        Verify that an 404 is returned if the enterprise customer specified in the URL does not exist in the database.
        """
        mock_chat_completion.return_value = 'Test Response.'
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)
        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        # call the endpoint without creation enterprise customer in the database.
        response = self.client.post(self.url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @mock.patch('enterprise.models.chat_completion')
    def test_view_returns_error_when_payload_is_not_valid(self, mock_chat_completion):
        """
        Verify that the endpoint returns an error response in case of invalid/missing data.
        """
        mock_chat_completion.return_value = 'Test Response.'
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        EnterpriseCustomerFactory.create(uuid=self.enterprise_uuid)

        response = self.client.post(self.url, data={}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.json()

        errors = response.json()['errors']
        assert 'learner_progress' in errors
        assert 'learner_engagement' in errors

    @mock.patch('enterprise.models.chat_completion')
    def test_view(self, mock_chat_completion):
        """
        Verify the behavior of the endpoint.
        """
        mock_chat_completion.return_value = 'Test Response.'
        enterprise_customer = EnterpriseCustomerFactory.create()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, enterprise_customer.uuid)
        url = settings.TEST_SERVER + reverse(
            self.ANALYTICS_SUMMARY_ENDPOINT, kwargs={'enterprise_uuid': enterprise_customer.uuid}
        )

        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        response = self.client.post(url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'learner_progress' in response.json()
        assert 'learner_engagement' in response.json()

        # Make sure the 2 entries were added. one for learner progress and another for learner engagement
        assert ChatGPTResponse.objects.filter(enterprise_customer=enterprise_customer).count() == 2

        # Make sure further request with the same payload does not create another instance.
        response = self.client.post(url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'learner_progress' in response.json()
        assert 'learner_engagement' in response.json()

        assert ChatGPTResponse.objects.filter(enterprise_customer=enterprise_customer).count() == 2

    @mock.patch('enterprise.models.chat_completion')
    def test_view_with_inactive_contracts(self, mock_chat_completion):
        """
        Verify the behavior of the endpoint.
        """
        mock_chat_completion.return_value = 'Test Response.'
        payload = copy.deepcopy(self.payload)
        payload['learner_progress']['active_subscription_plan'] = False
        payload['learner_engagement']['active_contract'] = False
        enterprise_customer = EnterpriseCustomerFactory.create()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, enterprise_customer.uuid)
        url = settings.TEST_SERVER + reverse(
            self.ANALYTICS_SUMMARY_ENDPOINT, kwargs={'enterprise_uuid': enterprise_customer.uuid}
        )

        self.client.login(username=self.user.username, password=TEST_PASSWORD)

        response = self.client.post(url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'learner_progress' in response.json()
        assert 'learner_engagement' in response.json()

        # Make sure the 2 entries were added. one for learner progress and another for learner engagement
        assert ChatGPTResponse.objects.filter(enterprise_customer=enterprise_customer).count() == 2

        # Make sure further request with the same payload does not create another instance.
        response = self.client.post(url, data=self.payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'learner_progress' in response.json()
        assert 'learner_engagement' in response.json()

        assert ChatGPTResponse.objects.filter(enterprise_customer=enterprise_customer).count() == 2
