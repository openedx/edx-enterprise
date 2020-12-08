# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

import json
import logging
import os
import shutil
import unittest

import ddt
import mock
from edx_rest_api_client.exceptions import HttpClientError
from faker import Factory as FakerFactory
from opaque_keys.edx.keys import CourseKey
from pytest import mark, raises
from testfixtures import LogCapture

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage
from django.db.utils import IntegrityError
from django.http import QueryDict
from django.test.testcases import TransactionTestCase
from django.urls import reverse

from consent.errors import InvalidProxyConsent
from consent.helpers import get_data_sharing_consent
from consent.models import DataSharingConsent, ProxyDataSharingConsent
from enterprise.constants import ENTERPRISE_LEARNER_ROLE, ENTERPRISE_OPERATOR_ROLE
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCatalogQuery,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    LicensedEnterpriseCourseEnrollment,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
    logo_path,
)
from enterprise.utils import CourseEnrollmentDowngradeError, get_default_catalog_content_filter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from test_utils import assert_url, assert_url_contains_query_parameters, factories, fake_catalog_api


@mark.django_db
@ddt.ddt
class TestPendingEnrollment(unittest.TestCase):
    """
    Test for pending enrollment
    """
    def setUp(self):
        email = 'bob@jones.com'
        course_id = 'course-v1:edX+DemoX+DemoCourse'
        pending_link = factories.PendingEnterpriseCustomerUserFactory(user_email=email)
        self.enrollment = factories.PendingEnrollmentFactory(user=pending_link, course_id=course_id)
        self.user = factories.UserFactory(email=email)
        super(TestPendingEnrollment, self).setUp()

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = '<PendingEnrollment for email bob@jones.com in course with ID course-v1:edX+DemoX+DemoCourse>'
        assert expected_str == method(self.enrollment)


@mark.django_db
@ddt.ddt
class TestEnterpriseCourseEnrollment(unittest.TestCase):
    """
    Test for EnterpriseCourseEnrollment
    """
    def setUp(self):
        self.username = 'DarthVader'
        self.user = factories.UserFactory(username=self.username)
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=self.user.id)
        self.enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        super(TestEnterpriseCourseEnrollment, self).setUp()

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = (
            '<EnterpriseCourseEnrollment for user DarthVader in '
            'course with ID course-v1:edX+DemoX+DemoCourse>'
        )
        assert expected_str == method(self.enrollment)

    def test_get_enterprise_course_enrollment_id(self):
        """
        Test the get_enterprise_course_enrollment_id function.
        """
        course_enrollment = EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id(
            self.user,
            self.course_id,
            self.enterprise_customer_user.enterprise_customer
        )
        assert course_enrollment == self.enrollment.id

    def test_get_license_not_licensed_enrolled(self):
        """
        Test the license property on the Enterprise Course Enrollment
        """
        assert self.enrollment.license is None


@mark.django_db
class TestLicensedEnterpriseCourseEnrollment(unittest.TestCase):
    """
    Test for LicensedEnterpriseCourseEnrollment.
    """
    LICENSE_UUID = '730844c7-dee3-479d-bba8-b3e9ccc89518'

    def setUp(self):
        self.username = 'KyloRen'
        self.user = factories.UserFactory(username=self.username)
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=self.user.id)
        self.enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        self.licensed_enrollment = LicensedEnterpriseCourseEnrollment.objects.create(
            license_uuid=self.LICENSE_UUID,
            enterprise_course_enrollment=self.enrollment
        )
        super(TestLicensedEnterpriseCourseEnrollment, self).setUp()

    def test_create_license_enrollment_no_course_enrollment(self):
        """
        Test creating a LicensedEnterpriseCourseEnrollment without a Course Enrollment.
        """
        with raises(IntegrityError):
            self.licensed_enrollment = LicensedEnterpriseCourseEnrollment.objects.create(
                license_uuid=self.LICENSE_UUID
            )

    def test_get_license(self):
        """
        Test the license property on the Enterprise Course Enrollment.
        """
        assert self.enrollment.license.license_uuid == self.LICENSE_UUID


@mark.django_db
class TestEnterpriseCustomerManager(unittest.TestCase):
    """
    Tests for enterprise customer manager.
    """

    def tearDown(self):
        super(TestEnterpriseCustomerManager, self).tearDown()
        EnterpriseCustomer.objects.all().delete()  # pylint: disable=no-member

    def test_active_customers_get_queryset_returns_only_active(self):
        """
        Test that get_queryset on custom model manager returns only active customers.
        """
        customer1 = factories.EnterpriseCustomerFactory(active=True)
        customer2 = factories.EnterpriseCustomerFactory(active=True)
        inactive_customer = factories.EnterpriseCustomerFactory(active=False)

        active_customers = EnterpriseCustomer.active_customers.all()
        self.assertTrue(all(customer.active for customer in active_customers))
        self.assertIn(customer1, active_customers)
        self.assertIn(customer2, active_customers)
        self.assertNotIn(inactive_customer, active_customers)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomer`` conversion to string.
        """
        customer = factories.EnterpriseCustomerFactory()
        expected_to_str = "<EnterpriseCustomer {code:x}: {name}>".format(
            code=customer.uuid.time_low, name=customer.name
        )
        self.assertEqual(method(customer), expected_to_str)

    def test_identity_providers(self):
        """
        Test identity_provider and identity_providers property returns correct value without errors.
        """
        customer = factories.EnterpriseCustomerFactory()
        ent_idp_one = factories.EnterpriseCustomerIdentityProviderFactory(enterprise_customer=customer)
        ent_idp_two = factories.EnterpriseCustomerIdentityProviderFactory(enterprise_customer=customer)
        assert customer.identity_providers[0] == ent_idp_one
        assert customer.identity_providers[1] == ent_idp_two

    def test_no_identity_provider(self):
        """
        Test identity_provider property returns correct value without errors.

        Test that identity_provider property does not raise ObjectDoesNotExist and returns False
        if enterprise customer does not have an associated identity provider.
        """
        assert factories.EnterpriseCustomerFactory().has_identity_providers is False

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_catalog_contains_course_with_enterprise_customer_catalog(self, api_client_mock):
        """
        Test EnterpriseCustomer.catalog_contains_course with a related EnterpriseCustomerCatalog.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerCatalogFactory(enterprise_customer=enterprise_customer)

        # Test when content is in the enterprise customer's catalog(s)
        api_client_mock.return_value.enterprise_contains_content_items.return_value = True
        assert enterprise_customer.catalog_contains_course(fake_catalog_api.FAKE_COURSE_RUN['key']) is True

        # Test when content is NOT in the enterprise customer's catalog(s)
        api_client_mock.return_value.enterprise_contains_content_items.return_value = False
        assert enterprise_customer.catalog_contains_course(fake_catalog_api.FAKE_COURSE_RUN['key']) is False

    @mock.patch('enterprise.utils.UserPreference', return_value=mock.MagicMock())
    def test_unset_language_of_all_enterprise_learners(self, user_preference_mock):
        """
        Validate that unset_language_of_all_enterprise_learners is called whenever default_language changes.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory()
        user_preference_mock.objects.filter.assert_called_once()

        # Make sure `unset_language_of_all_enterprise_learners` is called each time `default_language` changes.
        enterprise_customer.default_language = 'es-417'
        enterprise_customer.save()
        assert user_preference_mock.objects.filter.call_count == 2

        # make sure `unset_language_of_all_enterprise_learners` is not called if `default_language` is
        # not changed.
        enterprise_customer.default_language = 'es-417'
        enterprise_customer.save()
        assert user_preference_mock.objects.filter.call_count == 2

        # Make sure `unset_language_of_all_enterprise_learners` is not called if `default_language` is
        # set to `None`.
        enterprise_customer.default_language = None
        enterprise_customer.save()
        assert user_preference_mock.objects.filter.call_count == 2


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerUserManager(unittest.TestCase):
    """
    Tests EnterpriseCustomerUserManager.
    """

    def test_get_returns_only_one_when_multiple_objects_returned(self):
        """
        Test that get on custom model manager returns only the active object when multiple objects found.
        """
        enterprise_customer1 = factories.EnterpriseCustomerFactory()
        enterprise_customer2 = factories.EnterpriseCustomerFactory()
        user = factories.UserFactory(email='albert.einstein@princeton.edu')
        first_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer1,
            user_id=user.id
        )
        second_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer2,
            user_id=user.id,
            active=False
        )
        all_customer_users = [first_customer_user, second_customer_user]
        fetched_object = EnterpriseCustomerUser.objects.get(user_id=user.id)
        self.assertIn(fetched_object, all_customer_users)
        self.assertEqual(fetched_object.active, True)
        EnterpriseCustomerUser.objects.filter(user_id=user.id).delete()
        with raises(EnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.get(user_id=user.id)

    @ddt.data("albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu")
    def test_link_user_existing_user(self, user_email):
        enterprise_customer = factories.EnterpriseCustomerFactory()
        user = factories.UserFactory(email=user_email)
        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no link records should exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=user_email).count() == 0, \
            "Precondition check: no pending link records should exist"

        # Verify that no enterprise role assignment record is present for the user.
        enterprise_learner_role = SystemWideEnterpriseRole.objects.get(name=ENTERPRISE_LEARNER_ROLE)
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            role=enterprise_learner_role
        )
        assert not learner_role_assignment.exists()

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_id=user.id
        )
        assert actual_records.count() == 1
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "No pending links should have been created"

        # Also verify that enterprise role assignment record is created for the user.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            role=enterprise_learner_role
        )
        assert learner_role_assignment.exists()

    @ddt.data("yoda@jeditemple.net", "luke_skywalker@resistance.org", "darth_vader@empire.com")
    def test_link_user_no_user(self, user_email):
        enterprise_customer = factories.EnterpriseCustomerFactory()

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no link records should exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=user_email).count() == 0, \
            "Precondition check: no pending link records should exist"

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = PendingEnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_email=user_email
        )
        assert actual_records.count() == 1
        assert EnterpriseCustomerUser.objects.count() == 0, "No pending link records should have been created"

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_linked_user(self, email):
        user = factories.UserFactory(email=email)
        existing_link = factories.EnterpriseCustomerUserFactory(user_id=user.id)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_pending_link(self, email):
        existing_pending_link = factories.PendingEnterpriseCustomerUserFactory(user_email=email)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_pending_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_no_link(self, email):
        assert EnterpriseCustomerUser.objects.count() == 0
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) is None

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user(self, email):
        other_email = "other_email@example.com"
        user1, user2 = factories.UserFactory(email=email, id=1), factories.UserFactory(email=other_email, id=2)
        enterprise_customer1, enterprise_customer2 = (
            factories.EnterpriseCustomerFactory(),
            factories.EnterpriseCustomerFactory()
        )
        ecu1 = factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user1.id)
        ecu2 = factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user2.id)
        ecu3 = factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_id=user1.id)
        assert EnterpriseCustomerUser.objects.count() == 3
        for ecu in (ecu1, ecu2, ecu3):
            factories.EnterpriseCourseEnrollmentFactory(enterprise_customer_user=ecu)
        assert EnterpriseCourseEnrollment.objects.count() == 3

        query_method = EnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer1, email)
        # removes what was asked
        assert query_method(enterprise_customer=enterprise_customer1, user_id=user1.id).count() == 0
        # keeps records of the same user with different EC (though it shouldn't be the case)
        assert query_method(enterprise_customer=enterprise_customer2, user_id=user1.id).count() == 1
        # keeps records of other users
        assert query_method(user_id=user2.id).count() == 1

        # Verify that actual `EnterpriseCustomerUser` still present in database because it was soft deleted
        soft_deleted_ecu = EnterpriseCustomerUser.all_objects.get(
            enterprise_customer=enterprise_customer1,
            user_id=user1.id
        )
        # Verify that related `EnterpriseCourseEnrollment` records still present in database
        soft_deleted_ecu.linked = True
        soft_deleted_ecu.save()
        assert EnterpriseCourseEnrollment.objects.filter(enterprise_customer_user=soft_deleted_ecu).count() == 1
        # Verify that all `EnterpriseCourseEnrollment` records are present
        assert EnterpriseCourseEnrollment.objects.count() == 3

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_pending_link(self, email):
        other_email = "other_email@example.com"
        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=email)
        factories.PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=other_email)
        assert PendingEnterpriseCustomerUser.objects.count() == 2

        query_method = PendingEnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)
        # removes what was asked
        assert query_method(enterprise_customer=enterprise_customer, user_email=email).count() == 0
        # keeps records of other users
        assert query_method(user_email=other_email).count() == 1

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user_no_link(self, email):
        user = factories.UserFactory(email=email)
        enterprise_customer = factories.EnterpriseCustomerFactory()
        query_method = EnterpriseCustomerUser.objects.filter

        assert query_method(user_id=user.id).count() == 0, "Precondition check: link record exists"

        with raises(EnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_no_user_no_pending_link(self, email):
        enterprise_customer = factories.EnterpriseCustomerFactory()
        query_method = PendingEnterpriseCustomerUser.objects.filter

        assert query_method(user_email=email).count() == 0, "Precondition check: link record exists"

        with raises(PendingEnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerUser model.
    """

    def setUp(self):
        """
        Test set up
        """
        super(TestEnterpriseCustomerUser, self).setUp()
        self.worker_user = factories.UserFactory(
            username=settings.ENTERPRISE_SERVICE_WORKER_USERNAME, is_staff=True, is_active=True
        )
        self.user = factories.UserFactory(username='Batman')
        self.order_create_log_message = 'Creating order for enterprise learner with id [{}] for enrollment in course ' \
                                        'with id: [{}], [percentage discount] [{}] and [sales_force_id] [{}]'

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_id = 15, 12
        customer_user = factories.EnterpriseCustomerUserFactory(id=customer_user_id, user_id=user_id)
        expected_to_str = "<EnterpriseCustomerUser {ID}>: {enterprise_name} - {user_id}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_id=user_id
        )
        self.assertEqual(method(customer_user), expected_to_str)

    @ddt.data("albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu")
    def test_user_property_user_exists(self, email):
        user_instance = factories.UserFactory(email=email)
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user_instance.id)
        assert enterprise_customer_user.user == user_instance

    @ddt.data(10, 42, 1138)
    def test_user_property_user_missing(self, user_id):
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user_id)
        assert enterprise_customer_user.user is None

    @ddt.data("albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu")
    def test_user_email_property_user_exists(self, email):
        user = factories.UserFactory(email=email)
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user.id)
        assert enterprise_customer_user.user_email == email

    def test_user_email_property_user_missing(self):
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=42)
        assert enterprise_customer_user.user_email is None

    @ddt.data("alberteinstein", "richardfeynman", "leosusskind")
    def test_username_property_user_exists(self, username):
        user_instance = factories.UserFactory(username=username)
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user_instance.id)
        assert enterprise_customer_user.username == username

    def test_username_property_user_missing(self):
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=42)
        assert enterprise_customer_user.username is None

    @ddt.data(
        (None, None, False),
        ('fake-identity', 'saml-user-id', True),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.ThirdPartyAuthApiClient')
    def test_get_remote_id(self, provider_id, expected_value, called, mock_third_party_api):
        user = factories.UserFactory(username="hi")
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user.id)
        if provider_id:
            factories.EnterpriseCustomerIdentityProviderFactory(
                provider_id=provider_id,
                enterprise_customer=enterprise_customer_user.enterprise_customer
            )
        mock_third_party_api.return_value.get_remote_id.return_value = 'saml-user-id'
        actual_value = enterprise_customer_user.get_remote_id()
        assert actual_value == expected_value
        if called:
            mock_third_party_api.return_value.get_remote_id.assert_called_once_with(provider_id, "hi")
        else:
            assert mock_third_party_api.return_value.get_remote_id.call_count == 0

    @mock.patch('enterprise.utils.segment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCustomerUser.create_order_for_enrollment')
    @ddt.data('audit', 'verified')
    def test_enroll_learner(self, course_mode, enrollment_order_mock, enrollment_api_client_mock, analytics_mock):
        """
        ``enroll_learner`` enrolls the learner and redirects to the LMS courseware.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = None
        enterprise_customer_user.enroll('course-v1:edX+DemoX+Demo_Course', course_mode)
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_called_once()
        analytics_mock.track.assert_called_once()
        if course_mode == 'verified':
            enrollment_order_mock.assert_called_once()
        else:
            enrollment_order_mock.assert_not_called()

    @mock.patch('enterprise.utils.segment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCustomerUser.create_order_for_enrollment')
    def test_enroll_failure_with_no_order(self, enrollment_order_mock, enrollment_api_client_mock, analytics_mock):
        """
        ``enroll_learner`` cannot enroll due to api client error. Orders in ecommerce and EnterpriseCourseEnrollment
         remain unmodified.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enrollment_api_client_mock.return_value.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "Enrollment error"}).encode()
        )
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = None
        enterprise_enrollment_count = EnterpriseCourseEnrollment.objects.count()
        with LogCapture(level=logging.ERROR) as log_capture:
            enterprise_customer_user.enroll('course-v1:edX+DemoX+Demo_Course', 'verified')
            enrollment_api_client_mock.return_value.enroll_user_in_course.assert_called_once()
            analytics_mock.track.assert_not_called()
            enrollment_order_mock.assert_not_called()
            assert 'Enrollment error' in log_capture.records[0].getMessage()
            self.assertEqual(EnterpriseCourseEnrollment.objects.count(), enterprise_enrollment_count)

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCustomerUser.create_order_for_enrollment')
    def test_enroll_learner_already_enrolled(self, enrollment_order_mock, enrollment_api_client_mock):
        """
        ``enroll_learner`` does not enroll the user, as they're already enrolled, and redirects to the LMS courseware.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'audit'
        }
        enterprise_customer_user.enroll('course-v1:edX+DemoX+Demo_Course', 'audit')
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_not_called()
        enrollment_order_mock.assert_not_called()

    @mock.patch('enterprise.utils.segment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.models.EnterpriseCustomerUser.create_order_for_enrollment')
    def test_enroll_learner_upgrade_mode(self, enrollment_order_mock, enrollment_api_client_mock, analytics_mock):
        """
        ``enroll_learner`` enrolls the learner to a paid mode from previously being enrolled in audit.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'audit'
        }
        enterprise_customer_user.enroll('course-v1:edX+DemoX+Demo_Course', 'verified')
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_called_once()
        analytics_mock.track.assert_called_once()
        enrollment_order_mock.assert_called_once()

    @mock.patch('enterprise.models.EnrollmentApiClient')
    def test_enroll_learner_downgrade_mode(self, enrollment_api_client_mock):
        """
        ``enroll_learner`` does not enroll the user, as they're already enrolled, and redirects to the LMS courseware.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'verified'
        }
        with self.assertRaises(CourseEnrollmentDowngradeError):
            enterprise_customer_user.enroll('course-v1:edX+DemoX+Demo_Course', 'audit')

        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_not_called()

    @mock.patch('enterprise.models.get_ecommerce_worker_user')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    @mock.patch('enterprise.api_client.ecommerce.EcommerceApiClient.create_manual_enrollment_orders')
    def test_create_order_for_enrollment(self, utils_mock, ecommerce_api_client_init_mock,  # pylint: disable=unused-argument
                                         ecommerce_api_client_call_mock):  # pylint: disable=unused-argument
        """
        Test that expected logs appear when we try to create an order for a course while enrolling an enterprise user.
        """
        discount = 10.0
        sales_force_id = 'dummy-sales_force_id'
        mode = "verified"
        user = factories.UserFactory()
        utils_mock.return_value = user
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        course_run_id = 'course-v1:edX+DemoX+Demo_Course'

        expected_msg = self.order_create_log_message.format(
            enterprise_customer_user.user_id,
            course_run_id,
            discount,
            sales_force_id
        )

        with LogCapture(level=logging.DEBUG) as log_capture:
            enterprise_customer_user.create_order_for_enrollment(course_run_id, discount, mode, sales_force_id)
            assert expected_msg in log_capture.records[0].getMessage()

    @mock.patch('enterprise.models.get_ecommerce_worker_user')
    def test_create_order_error_cannot_retrieve_service_worker(self, utils_mock):
        discount = 100.0
        sales_force_id = 'other-sales_force_id'
        mode = "verified"
        utils_mock.return_value = None
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        course_run_id = 'course-v1:edX+DemoX+Demo_Course'

        expected_messages = [
            self.order_create_log_message.format(
                enterprise_customer_user.user_id,
                course_run_id,
                discount,
                sales_force_id
            ),
            'Could not create order for enterprise learner with id [{}] for enrollment in course with id [{}]. Reason: '
            '[{}]'.format(
                enterprise_customer_user.user_id,
                course_run_id,
                'Failed to retrieve a valid ecommerce worker.')
        ]

        with LogCapture(level=logging.DEBUG) as log_capture:
            enterprise_customer_user.create_order_for_enrollment(course_run_id, discount, mode, sales_force_id)
            for index, message in enumerate(expected_messages):
                assert message in log_capture.records[index].getMessage()

    @mock.patch('enterprise.models.get_ecommerce_worker_user')
    def test_create_order_error_cannot_create_ecommerce_api_client(self, utils_mock):
        discount = 0.0
        sales_force_id = 'another-sales_force_id'
        user = factories.UserFactory()
        mode = "verified"
        utils_mock.return_value = user
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        course_run_id = 'course-v1:edX+DemoX+Demo_Course'

        expected_messages = [
            self.order_create_log_message.format(
                enterprise_customer_user.user_id,
                course_run_id,
                discount,
                sales_force_id
            ),
            'edx-enterprise unexpectedly failed as if not installed in an OpenEdX platform',
            'Could not create order for enterprise learner with id [{}] for enrollment in course with id [{}]'.format(
                enterprise_customer_user.user_id,
                course_run_id),
        ]

        with LogCapture(level=logging.DEBUG) as log_capture:
            enterprise_customer_user.create_order_for_enrollment(course_run_id, discount, mode, sales_force_id)
            for index, message in enumerate(expected_messages):
                assert message in log_capture.records[index].getMessage()

    @ddt.data('get_or_create', 'update_or_create', 'create')
    def test_soft_delete(self, method_name):
        """
        Verify that `get_or_create/update_or_create/create` works as expected when an `EnterpriseCustomerUser`
        record is soft deleted.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=self.user.id, linked=False)
        ece = factories.EnterpriseCourseEnrollmentFactory(enterprise_customer_user=enterprise_customer_user)

        # `objects` manager should not return any linked=False record
        assert not EnterpriseCustomerUser.objects.filter(pk=enterprise_customer_user.pk).exists()

        queryset_method = getattr(EnterpriseCustomerUser.objects, method_name)
        result = queryset_method(
            enterprise_customer=enterprise_customer_user.enterprise_customer,
            user_id=enterprise_customer_user.user_id
        )

        ecu, created = (result, True) if method_name == 'create' else (result[0], result[1])
        # `EnterpriseCustomerUser` record should be linked=True and related `EnterpriseCourseEnrollment` should exist
        assert created
        assert ecu.linked
        assert EnterpriseCourseEnrollment.objects.filter(pk=ece.pk).exists()

        # These methods should not raise any exception if called successively
        if method_name in ('get_or_create', 'update_or_create'):
            for __ in range(2):
                ecu, created = queryset_method(
                    enterprise_customer=enterprise_customer_user.enterprise_customer,
                    user_id=enterprise_customer_user.user_id
                )

                assert not created
                assert ecu.linked
        elif method_name in ('create',):
            # create should raise exception if called successively
            with self.assertRaises(IntegrityError):
                for __ in range(2):
                    result = queryset_method(
                        enterprise_customer=enterprise_customer_user.enterprise_customer,
                        user_id=enterprise_customer_user.user_id
                    )

    @mock.patch('enterprise.utils.UserPreference', return_value=mock.MagicMock())
    def test_unset_enterprise_learner_language(self, user_preference_mock):
        """
        Validate that unset_enterprise_learner_language is called whenever a nwe learner is linked to an enterprise
        customer with Non-Null default language.
        """
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        user_preference_mock.objects.update_or_create.assert_called_once()

        # Make sure `unset_enterprise_learner_language` is not called if the enterprise customer does not have a
        # default_language.
        enterprise_customer_user.enterprise_customer.default_language = None
        enterprise_customer_user.enterprise_customer.save()
        factories.EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer_user.enterprise_customer
        )

        assert user_preference_mock.objects.update_or_create.call_count == 1


@mark.django_db
@ddt.ddt
class TestPendingEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the PendingEnterpriseCustomerUser model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_email = 15, "some_email@example.com"
        customer_user = factories.PendingEnterpriseCustomerUserFactory(id=customer_user_id, user_email=user_email)
        expected_to_str = "<PendingEnterpriseCustomerUser {ID}>: {enterprise_name} - {user_email}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_email=user_email
        )
        self.assertEqual(method(customer_user), expected_to_str)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerBrandingConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerBrandingConfiguration model.
    """

    @staticmethod
    def _make_file_mock(name="logo.png", size=240 * 1024):
        """
        Build file mock.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = name
        file_mock.size = size
        return file_mock

    def cleanup(self):
        """Remove the temp directory only if it exists."""
        dir_name = os.path.abspath('enterprise/branding/')
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        file_mock = self._make_file_mock()
        customer_branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1, logo=file_mock, enterprise_customer=factories.EnterpriseCustomerFactory()
        )
        expected_str = "<EnterpriseCustomerBrandingConfiguration {ID}>: {enterprise_name}".format(
            ID=customer_branding_config.id,
            enterprise_name=customer_branding_config.enterprise_customer.name,
        )
        self.assertEqual(method(customer_branding_config), expected_str)

    @ddt.data(
        (True, True),
        (False, False),
    )
    @ddt.unpack
    def test_logo_path(self, file_exists, delete_called):
        """
        Test that the path of image file should beenterprise/branding/<model.id>/<model_id>_logo.<ext>.lower().

        Additionally, test that the correct backend actions are taken in regards to deleting existing data.
        """
        file_mock = self._make_file_mock()
        branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1,
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo=file_mock
        )

        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        storage_mock.exists.return_value = file_exists
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            path = logo_path(branding_config, branding_config.logo.name)
            self.assertEqual(path, "enterprise/branding/1/1_logo.png")
            assert storage_mock.delete.call_count == (1 if delete_called else 0)
            if delete_called:
                storage_mock.delete.assert_called_once_with('enterprise/branding/1/1_logo.png')

    def test_logo_path_after_save(self):
        """
        Test that `EnterpriseCustomerBrandingConfiguration`.logo is saved at the correct path with correct id after the
        model instance is saved.
        """
        file_mock = self._make_file_mock()
        branding_config = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo=file_mock
        )
        branding_config.save()
        saved_path = branding_config.logo.path  # pylint: disable=no-member
        expected_path = os.path.abspath(logo_path(branding_config, branding_config.logo.name))
        self.assertEqual(saved_path, expected_path)
        self.addCleanup(self.cleanup)

    def test_branding_configuration_saving_successfully(self):
        """
        Test enterprise customer branding configuration saving successfully.
        """
        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        branding_config_1 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo="test1.png"
        )

        storage_mock.exists.return_value = True
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            branding_config_1.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 1)

        branding_config_2 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo="test2.png"
        )

        storage_mock.exists.return_value = False
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            branding_config_2.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 2)

    def test_branding_configuration_editing(self):
        """
        Test enterprise customer branding configuration saves changes to existing instance.
        """
        configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo="test1.png"
        )
        configuration.save()
        self.assertEqual(configuration.logo.url, '/test1.png')  # pylint: disable=no-member
        configuration.logo = 'test2.png'
        configuration.save()
        self.assertEqual(configuration.logo.url, '/test2.png')  # pylint: disable=no-member

    @ddt.data(
        (False, 2048),
        (False, 1024),
        (True, 512),
        (True, 256),
        (True, 128),
    )
    @ddt.unpack
    def test_image_size(self, is_valid_image_size, image_size):
        """
        Test image size in KB's, image_size < 512 KB.
        Default valid max image size is 512 KB (512 * 1024 bytes).
        See config `valid_max_image_size` in apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1.png"
        file_mock.size = image_size * 1024  # image size in bytes
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not is_valid_image_size:
            with self.assertRaises(ValidationError) as validation_error:
                branding_configuration.full_clean()

            expected_validation_message = 'The logo image file size must be less than or equal to 512 KB.'
            self.assertEqual(validation_error.exception.messages[0], expected_validation_message)
        else:
            branding_configuration.full_clean()  # exception here will fail the test

    @ddt.data(
        (False, ".jpg"),
        (False, ".gif"),
        (False, ".bmp"),
        (True, ".png"),
    )
    @ddt.unpack
    def test_image_type(self, is_valid_image_extension, image_extension):
        """
        Test image type, currently .png is supported in configuration. see apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1" + image_extension
        file_mock.size = 2 * 1024
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not is_valid_image_extension:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test

    @ddt.data(
        (False, '#00bb2'),
        (False, '#'),
        (False, '#00bb22C'),
        (False, '00bb22C'),
        (False, '00bb22CD'),
        (False, '#AABHCC'),
        (True, '#AABBCC'),
        (True, '#AaBbCc'),
        (True, '#0F23C7'),
    )
    @ddt.unpack
    def test_hex_color(self, is_valid_hex_color, hex_string):
        """
        Test hex color validator.
        """
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            primary_color=hex_string,
            secondary_color=hex_string,
            tertiary_color=hex_string,
        )

        if not is_valid_hex_color:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerIdentityProvider(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerIdentityProvider model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerIdentityProvider`` conversion to string.
        """
        provider_id, enterprise_customer_name = "saml-test", "TestShib"
        enterprise_customer = factories.EnterpriseCustomerFactory(name=enterprise_customer_name)
        ec_idp = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=enterprise_customer,
            provider_id=provider_id,
        )

        expected_to_str = "<EnterpriseCustomerIdentityProvider {provider_id}>: {enterprise_name}".format(
            provider_id=provider_id,
            enterprise_name=enterprise_customer_name,
        )
        self.assertEqual(method(ec_idp), expected_to_str)

    @mock.patch("enterprise.models.utils.get_identity_provider")
    def test_provider_name(self, mock_method):
        """
        Test provider_name property returns correct value without errors..
        """
        faker = FakerFactory.create()
        provider_name = faker.name()
        mock_method.return_value.configure_mock(name=provider_name)
        ec_idp = factories.EnterpriseCustomerIdentityProviderFactory()

        assert ec_idp.provider_name == provider_name


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerCatalog(unittest.TestCase):
    """
    Tests for the EnterpriseCustomerCatalog model.
    """

    def setUp(self):
        """
        Setup tests
        """
        self.faker = FakerFactory.create()
        self.catalog_uuid = self.faker.uuid4()  # pylint: disable=no-member
        self.enterprise_uuid = self.faker.uuid4()  # pylint: disable=no-member
        self.enterprise_name = 'enterprisewithacatalog'
        super(TestEnterpriseCustomerCatalog, self).setUp()

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerCatalog`` conversion to string.
        """
        faker = FakerFactory.create()
        title = faker.name()  # pylint: disable=no-member
        name = 'EnterpriseWithACatalog'
        enterprise_catalog = EnterpriseCustomerCatalog(
            title=title,
            enterprise_customer=factories.EnterpriseCustomerFactory(name=name)
        )
        expected_str = "<EnterpriseCustomerCatalog '{title}' with UUID '{uuid}' for EnterpriseCustomer {name}>".format(
            title=title,
            uuid=enterprise_catalog.uuid,
            name=name
        )
        self.assertEqual(method(enterprise_catalog), expected_str)

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_catalog_param_in_course_enrollment_url(self, config_mock):
        """
        The ``get_course_enrollment_url`` method includes the ``catalog`` query string param.
        """
        config_mock.get_value.return_value = 'value'
        course_key = 'edX+DemoX'

        course_enrollment_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.enterprise_uuid, course_key],
        )
        querystring_dict = QueryDict('', mutable=True)
        querystring_dict.update({
            'utm_medium': 'enterprise',
            'utm_source': self.enterprise_name,
            'catalog': self.catalog_uuid,
        })
        expected_course_enrollment_url = '{course_enrollment_url}?{querystring}'.format(
            course_enrollment_url=course_enrollment_url,
            querystring=querystring_dict.urlencode()
        )

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            )
        )
        enrollment_url = enterprise_catalog.get_course_enrollment_url(course_key=course_key)
        assert_url(enrollment_url, expected_course_enrollment_url)

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_audit_param_in_course_enrollment_url(self, config_mock):
        """
        The ``get_course_enrollment_url`` method includes the ``audit=true`` query string param when
        publish_audit_enrollment_urls is enabled for the EnterpriseCustomerCatalog.
        """
        config_mock.get_value.return_value = 'value'
        course_key = 'edX+DemoX'

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            ),
            publish_audit_enrollment_urls=True
        )
        enrollment_url = enterprise_catalog.get_course_enrollment_url(course_key=course_key)
        assert_url_contains_query_parameters(enrollment_url, {'audit': 'true'})

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_catalog_param_in_course_run_enrollment_url(self, config_mock):
        """
        The ``get_course_run_enrollment_url`` method includes the ``catalog`` query string param.
        """
        config_mock.get_value.return_value = 'value'
        course_run_id = 'course-v1:edX+DemoX+Demo_Course_1'
        course_run_key = CourseKey.from_string(course_run_id)

        course_enrollment_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[self.enterprise_uuid, course_run_id],
        )
        querystring_dict = QueryDict('', mutable=True)
        querystring_dict.update({
            'utm_medium': 'enterprise',
            'utm_source': self.enterprise_name,
            'catalog': self.catalog_uuid,
        })
        expected_course_enrollment_url = '{course_enrollment_url}?{querystring}'.format(
            course_enrollment_url=course_enrollment_url,
            querystring=querystring_dict.urlencode()
        )

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            )
        )
        enrollment_url = enterprise_catalog.get_course_run_enrollment_url(course_run_key=course_run_key)
        assert_url(enrollment_url, expected_course_enrollment_url)

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_audit_param_in_course_run_enrollment_url(self, config_mock):
        """
        The ``get_course_run_enrollment_url`` method returns ``audit=true`` in the query string when
        publish_audit_enrollment_urls is enabled for the EnterpriseCustomerCatalog
        """
        config_mock.get_value.return_value = 'value'
        course_run_id = 'course-v1:edX+DemoX+Demo_Course_1'
        course_run_key = CourseKey.from_string(course_run_id)

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            ),
            publish_audit_enrollment_urls=True
        )
        enrollment_url = enterprise_catalog.get_course_run_enrollment_url(course_run_key=course_run_key)
        assert_url_contains_query_parameters(enrollment_url, {'audit': 'true'})

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_catalog_param_in_program_enrollment_url(self, config_mock):
        config_mock.get_value.return_value = 'value'
        program_uuid = fake_catalog_api.FAKE_PROGRAM_RESPONSE1.get('uuid')

        program_enrollment_url = reverse(
            'enterprise_program_enrollment_page',
            args=[self.enterprise_uuid, program_uuid],
        )
        querystring_dict = QueryDict('', mutable=True)
        querystring_dict.update({
            'utm_medium': 'enterprise',
            'utm_source': self.enterprise_name,
            'catalog': self.catalog_uuid,
        })
        expected_program_enrollment_url = '{program_enrollment_url}?{querystring}'.format(
            program_enrollment_url=program_enrollment_url,
            querystring=querystring_dict.urlencode()
        )

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            )
        )
        enrollment_url = enterprise_catalog.get_program_enrollment_url(program_uuid=program_uuid)
        assert_url(enrollment_url, expected_program_enrollment_url)

    @mock.patch('enterprise.utils.configuration_helpers')
    def test_audit_param_in_program_enrollment_url(self, config_mock):
        """
        The ``get_program_enrollment_url`` method returns ``audit=true`` in the query string when
        publish_audit_enrollment_urls is enabled for the EnterpriseCustomerCatalog
        """
        config_mock.get_value.return_value = 'value'
        program_uuid = fake_catalog_api.FAKE_PROGRAM_RESPONSE1.get('uuid')

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=self.catalog_uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(
                uuid=self.enterprise_uuid,
                name=self.enterprise_name
            ),
            publish_audit_enrollment_urls=True
        )
        enrollment_url = enterprise_catalog.get_program_enrollment_url(program_uuid=program_uuid)
        assert_url_contains_query_parameters(enrollment_url, {'audit': 'true'})

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_get_course_and_course_run_no_content_items(self, api_client_mock):
        """
        Verify the `get_course_and_course_run` method returns a tuple (None, None) when no content items exist.
        """
        api_client_mock.return_value.contains_content_items.return_value = False

        enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()
        assert enterprise_customer_catalog.get_course_and_course_run('fake-course-run-id') == (None, None)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_get_course_run_no_content_items(self, api_client_mock):
        """
        Verify the `get_course_run` method returns None if no content items exist.
        """
        api_client_mock.return_value.contains_content_items.return_value = False

        enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()
        assert enterprise_customer_catalog.get_course_run('fake-course-run-id') is None

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_get_course_no_content_items(self, api_client_mock):
        """
        Verify the `get_course` method returns None if no content items exist.
        """
        api_client_mock.return_value.contains_content_items.return_value = False

        enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()
        assert enterprise_customer_catalog.get_course('fake-course-id') is None

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_get_program_no_content_items(self, api_client_mock):
        """
        Verify the `get_program` method returns None if no content items exist.
        """
        api_client_mock.return_value.contains_content_items.return_value = False

        enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()
        assert enterprise_customer_catalog.get_program('fake-uuid') is None

    def test_title_length(self):
        """
        Test `EnterpriseCustomerCatalog.title` field can take 255 characters.
        """
        faker = FakerFactory.create()
        uuid = faker.uuid4()  # pylint: disable=no-member
        title = faker.text(max_nb_chars=255)  # pylint: disable=no-member

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            title=title
        )
        enterprise_catalog.save()
        assert EnterpriseCustomerCatalog.objects.get(uuid=uuid).title == title

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_paginated_content_uses_total_count_from_response(self, mock_catalog_api_class):
        """
        Test EnterpriseCustomerCatalog.get_paginated_content should use the count value
        provided by the discovery service API response, and not just count the length
        of the results of the current page
        """
        mock_catalog_api = mock_catalog_api_class.return_value
        mock_catalog_api.is_course_in_catalog.return_value = False
        mock_catalog_api.get_catalog_results.return_value = {
            'results': [fake_catalog_api.FAKE_COURSE_RUN],
            'next': 'some_next_url',
            'count': 129381,
            'previous': None,
        }

        faker = FakerFactory.create()
        uuid = faker.uuid4()  # pylint: disable=no-member
        title = faker.text(max_nb_chars=255)  # pylint: disable=no-member

        enterprise_catalog = EnterpriseCustomerCatalog(
            uuid=uuid,
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            title=title
        )
        enterprise_catalog.save()

        response = enterprise_catalog.get_paginated_content(QueryDict())
        assert response['count'] == 129381  # Previously this would have been 1

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_exclude_expired_course_run_in_api_query_param(self, mock_catalog_api_class):
        """
        Test EnterpriseCustomerCatalog.get_paginated_content should pass the exclude_expired_course_runs query param to
        the discovery service API
        """
        mock_catalog_api = mock_catalog_api_class.return_value
        enterprise_catalog = factories.EnterpriseCustomerCatalogFactory()
        enterprise_catalog.get_paginated_content(QueryDict())
        default_catalog_content_filter = get_default_catalog_content_filter()
        query_param = {"exclude_expired_course_run": True}
        mock_catalog_api.get_catalog_results.assert_called_with(default_catalog_content_filter, query_param)

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_contains_programs(self, mock_catalog_api_class):
        """
        Test EnterpriseCustomerCatalog.contains_programs.
        """
        mock_catalog_api = mock_catalog_api_class.return_value
        mock_catalog_api.get_catalog_results.return_value = {'results': [fake_catalog_api.FAKE_PROGRAM_RESPONSE1]}

        catalog = factories.EnterpriseCustomerCatalogFactory()
        assert catalog.contains_programs([fake_catalog_api.FAKE_PROGRAM_RESPONSE1['uuid']]) is True

        mock_catalog_api.get_catalog_results.return_value = {}
        assert catalog.contains_programs([fake_catalog_api.FAKE_PROGRAM_RESPONSE1['uuid']]) is False

    def test_get_content_filter(self):
        """
        Test `get_content_filter` method of `EnterpriseCustomerCatalog` model should return content filter
        of its own if there is no `EnterpriseCatalogQuery` is linked to it. If there is a linked
        `EnterpriseCatalogQuery` then it should return content filter of linked `EnterpriseCatalogQuery`.
        """
        catalog_query_content_filter = {"content_type": "course", "partner": "edx"}
        catalog_content_filter = {"content_type": "course_run", "partner": "dummy"}
        catalog_query = factories.EnterpriseCatalogQueryFactory(content_filter=catalog_query_content_filter)
        catalog = factories.EnterpriseCustomerCatalogFactory(content_filter=catalog_content_filter)
        self.assertEqual(catalog.get_content_filter(), catalog_content_filter)

        catalog.enterprise_catalog_query = catalog_query
        catalog.save()
        self.assertEqual(catalog.get_content_filter(), catalog_query_content_filter)

    @ddt.data(
        {
            'content_filter': {'key': 'coursev1:course1'},
            'error': ["Content filter 'key' must be of type <class 'list'>"]
        },
        {
            'content_filter': {'aggregation_key': 'courserun:course'},
            'error': ["Content filter 'aggregation_key' must be of type <class 'list'>"],
        },
        {
            'content_filter': {'first_enrollable_paid_seat_price__lte': [12]},
            'error': ["Content filter 'first_enrollable_paid_seat_price__lte' must be of type <class 'str'>"]
        },
        {
            'content_filter': {'key': [3, 'course']},
            'error': ["Content filter 'key' must contain values of type <class 'str'>"]
        }
    )
    @ddt.unpack
    def test_save_content_filter_fail(self, content_filter, error):
        fail_catalog = factories.EnterpriseCustomerCatalogFactory(content_filter=content_filter)
        try:
            fail_catalog.full_clean()
        except ValidationError as validation_error:
            assert sorted(validation_error.messages) == sorted(error)


@mark.django_db
@ddt.ddt
class TestEnrollmentNotificationEmailTemplate(unittest.TestCase):
    """
    Tests of the EnrollmentNotificationEmailTemplate model.
    """

    def setUp(self):
        self.template = EnrollmentNotificationEmailTemplate.objects.create(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            plaintext_template=(
                'This is a template - testing {{ course_name }}, {{ other_value }}'
            ),
            html_template=(
                '<b>This is an HTML template! {{ course_name }}!!!</b>'
            ),
        )
        super(TestEnrollmentNotificationEmailTemplate, self).setUp()

    def test_render_all_templates(self):
        plain, html = self.template.render_all_templates(
            {
                "course_name": "real course",
                "other_value": "filled in",
            }
        )
        assert plain == 'This is a template - testing real course, filled in'
        assert html == '<b>This is an HTML template! real course!!!</b>'

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = '<EnrollmentNotificationEmailTemplate for EnterpriseCustomer with UUID {}>'.format(
            self.template.enterprise_customer.uuid
        )
        assert expected_str == method(self.template)


@mark.django_db
class TestDataSharingConsentManager(unittest.TestCase):
    """
    Tests for the custom Data Sharing Consent Manager.
    """

    def setUp(self):
        super(TestDataSharingConsentManager, self).setUp()
        factories.DataSharingConsentFactory(
            enterprise_customer=factories.EnterpriseCustomerFactory(
                name='rich_enterprise'
            ),
            username='lowly_bob',
            course_id='hard_course_2017'
        )

    def test_get_returns_proxy_when_consent_doesnt_exist(self):
        """
        Test that ``proxied_get`` on custom manager returns a ``ProxyDataSharingConsent`` object when
        the searched-for ``DataSharingConsent`` object doesn't exist.
        """
        dsc = DataSharingConsent.objects.proxied_get(username='lowly_bob')
        proxy_dsc = DataSharingConsent.objects.proxied_get(username='optimistic_bob')
        assert isinstance(dsc, DataSharingConsent)
        assert isinstance(proxy_dsc, ProxyDataSharingConsent)
        assert dsc != proxy_dsc

    def test_get_returns_consent_when_it_exists(self):
        """
        Test that ``proxied_get`` on custom manager returns a ``DataSharingConsent`` object when the searched-for
        ``DataSharingConsent`` object exists.
        """
        dsc = DataSharingConsent.objects.proxied_get(username='lowly_bob')
        same_dsc = DataSharingConsent.objects.proxied_get(username='lowly_bob')
        assert isinstance(same_dsc, DataSharingConsent)
        assert dsc == same_dsc


@ddt.ddt
class TestProxyDataSharingConsent(TransactionTestCase):
    """
    Tests of the ``ProxyDataSharingConsent`` class (pseudo-model).
    """

    def setUp(self):
        super(TestProxyDataSharingConsent, self).setUp()
        self.proxy_dsc = ProxyDataSharingConsent(
            enterprise_customer=factories.EnterpriseCustomerFactory(
                name='rich_enterprise'
            ),
            username='lowly_bob',
            course_id='hard_course_2017'
        )

    @ddt.data('commit', 'save')
    def test_commit_and_synonyms(self, func):
        """
        Test that ``ProxyDataSharingConsent``'s ``commit`` method (and any synonyms) properly creates/saves/returns
        a new ``DataSharingConsent`` instance, and if updating an existing instance, returns that same model instance.
        """
        new_dsc = getattr(self.proxy_dsc, func)()
        no_new_dsc = getattr(self.proxy_dsc, func)()
        assert DataSharingConsent.objects.count() == 1
        assert DataSharingConsent.objects.all().first() == new_dsc
        assert no_new_dsc.pk == new_dsc.pk

    @ddt.data(
        {
            'enterprise_customer__name': 'rich_enterprise',
            'enterprise_customer__enable_data_sharing_consent': True,
        },
        {
            'enterprise_customer__name': 'rich_enterprise',
            'enterprise_customer__enable_data_sharing_consent': True,
            'lets_see_if__this': 'is_ignored',
        }
    )
    def test_create_new_proxy_with_composite_query(self, kwargs):
        """
        Test that we can use composite queries for enterprise customers.
        """
        proxy_dsc = ProxyDataSharingConsent(**kwargs)
        the_only_enterprise_customer = EnterpriseCustomer.objects.all().first()  # pylint: disable=no-member
        assert the_only_enterprise_customer == proxy_dsc.enterprise_customer

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``ProxyDataSharingConsent`` conversion to string
        """
        expected_to_str = "<ProxyDataSharingConsent for user lowly_bob of Enterprise rich_enterprise>"
        assert expected_to_str == method(self.proxy_dsc)

    def test_from_children_error(self):
        """
        Test ``ProxyDataSharingConsent.from_children`` method
        """
        with raises(InvalidProxyConsent):
            ProxyDataSharingConsent.from_children(
                'fake-program-id',
                mock.MagicMock(username='thing', enterprise_customer='otherthing'),
                mock.MagicMock(username='different_username', enterprise_customer='otherthing'),
            )

    @ddt.data(
        (
            'my_program_id',
            [
                mock.MagicMock(exists=False, granted=False, username='john', enterprise_customer='fake'),
                mock.MagicMock(exists=False, granted=False, username='john', enterprise_customer='fake'),
            ],
            {
                'exists': False,
                'granted': False
            }
        ),
        (
            'my_program_id',
            [
                mock.MagicMock(exists=False, granted=True, username='john', enterprise_customer='fake'),
                mock.MagicMock(exists=True, granted=True, username='john', enterprise_customer='fake'),
            ],
            {
                'exists': True,
                'granted': True
            }
        ),
        (
            'my_program_id',
            [
                mock.MagicMock(exists=True, granted=True, username='john', enterprise_customer='fake'),
                mock.MagicMock(exists=True, granted=False, username='john', enterprise_customer='fake'),
            ],
            {
                'exists': True,
                'granted': False
            }
        ),
        (
            'my_program_id',
            [
                mock.MagicMock(exists=True, granted=True, username='john', enterprise_customer='fake'),
                mock.MagicMock(exists=True, granted=True, username='john', enterprise_customer='fake'),
            ],
            {
                'exists': True,
                'granted': True
            }
        ),
    )
    @ddt.unpack
    def test_from_children(self, program_uuid, children, expected_attrs):
        proxy_dsc = ProxyDataSharingConsent.from_children(program_uuid, *children)
        for attr, val in expected_attrs.items():
            assert getattr(proxy_dsc, attr) == val

    @ddt.data(True, False)
    def test_consent_exists_proxy_enrollment(self, user_exists):
        """
        If we did proxy enrollment, we return ``True`` for the consent existence question.
        """
        if user_exists:
            factories.UserFactory(id=1)
        ece = factories.EnterpriseCourseEnrollmentFactory(enterprise_customer_user__user_id=1)
        consent_exists = get_data_sharing_consent(
            ece.enterprise_customer_user.username,
            ece.enterprise_customer_user.enterprise_customer.uuid,
            course_id=ece.course_id,
        ).exists
        if user_exists:
            assert consent_exists
        else:
            assert not consent_exists


@mark.django_db
@ddt.ddt
class TestDataSharingConsent(unittest.TestCase):
    """
    Tests of the ``DataSharingConsent`` model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``DataSharingConsent`` conversion to string
        """
        dsc = factories.DataSharingConsentFactory(
            enterprise_customer=factories.EnterpriseCustomerFactory(
                name='rich_enterprise'
            ),
            username='lowly_bob',
            course_id='hard_course_2017'
        )
        expected_to_str = "<DataSharingConsent for user lowly_bob of Enterprise rich_enterprise>"
        assert expected_to_str == method(dsc)


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerPluginConfiguration(unittest.TestCase):
    """
    Tests of the ``EnterpriseCustomerPluginConfiguration`` base model.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.config = EnterpriseCustomerPluginConfiguration(enterprise_customer=self.enterprise_customer)
        super(TestEnterpriseCustomerPluginConfiguration, self).setUp()

    def test_channel_code_raises(self):
        with raises(NotImplementedError):
            self.config.channel_code()

    @mock.patch('integrated_channels.integrated_channel.models.LearnerExporter')
    def test_get_learner_data_exporter(self, mock_learner_exporter):
        """
        The configuration returns the appropriate learner exporter.
        """
        mock_learner_exporter.return_value = 'mock_learner_exporter'
        assert self.config.get_learner_data_exporter(None) == 'mock_learner_exporter'

    @mock.patch('integrated_channels.integrated_channel.models.LearnerTransmitter')
    def test_get_learner_data_transmitter_raises(self, mock_learner_transmitter):
        """
        The configuration returns the appropriate learner transmitter.
        """
        mock_learner_transmitter.return_value = 'mock_learner_transmitter'
        assert self.config.get_learner_data_transmitter() == 'mock_learner_transmitter'

    @mock.patch('integrated_channels.integrated_channel.models.ContentMetadataExporter')
    def test_get_course_data_exporter_raises(self, mock_course_exporter):
        """
        The configuration returns the appropriate course exporter.
        """
        mock_course_exporter.return_value = 'mock_course_exporter'
        assert self.config.get_content_metadata_exporter(None) == 'mock_course_exporter'

    @mock.patch('integrated_channels.integrated_channel.models.ContentMetadataTransmitter')
    def test_get_course_data_transmitter_raises(self, mock_course_transmitter):
        """
        The configuration returns the appropriate course transmitter.
        """
        mock_course_transmitter.return_value = 'mock_course_transmitter'
        assert self.config.get_content_metadata_transmitter() == 'mock_course_transmitter'


@mark.django_db
@ddt.ddt
class TestLearnerDataTransmissionAudit(unittest.TestCase):
    """
    Tests of the LearnerDataTransmissionAudit model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``LearnerDataTransmissionAudit`` conversion to string
        """
        learner_data_audit = factories.LearnerDataTransmissionAuditFactory(
            id=1,
            enterprise_course_enrollment_id=1,
            course_id='course-id',
        )
        expected_to_str = '<LearnerDataTransmissionAudit 1 for enterprise enrollment 1, and course course-id>'
        assert expected_to_str == method(learner_data_audit)

    def test_provider_id(self):
        """
        The ``provier_id`` property is always ``None`` for the generic learner data transmission audit.
        """
        assert factories.LearnerDataTransmissionAuditFactory().provider_id is None

    def test_serialize(self):
        """
        The ``serialize`` method returns a generic JSON dump.
        """
        learner_data_audit = factories.LearnerDataTransmissionAuditFactory(
            course_id='course-id',
            completed_timestamp=999,
            grade='A+',
        )
        payload = (
            '{'
            '"completedTimestamp": 999, '
            '"courseCompleted": "true", '
            '"courseID": "course-id", '
            '"grade": "A+"'
            '}'
        )
        assert learner_data_audit.serialize() == payload


@mark.django_db
@ddt.ddt
class TestSapSuccessFactorsLearnerDataTransmissionAudit(unittest.TestCase):
    """
    Tests of the ``SapSuccessFactorsLearnerDataTransmissionAudit`` model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``SapSuccessFactorsLearnerDataTransmissionAudit`` conversion to string
        """
        learner_audit = factories.SapSuccessFactorsLearnerDataTransmissionAuditFactory(
            id=1,
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
        )
        expected_to_str = (
            "<SapSuccessFactorsLearnerDataTransmissionAudit 1 for enterprise enrollment 5, SAPSF user sap_user,"
            " and course course-v1:edX+DemoX+DemoCourse>"
        )
        assert expected_to_str == method(learner_audit)


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorsEnterpriseCustomerConfiguration(unittest.TestCase):
    """
    Tests of the SAPSuccessFactorsEnterpriseCustomerConfiguration model.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        self.config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
        )
        super(TestSAPSuccessFactorsEnterpriseCustomerConfiguration, self).setUp()

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` conversion to string
        """
        assert method(self.config) == "<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise GriffCo>"

    def test_channel_code(self):
        assert self.config.channel_code() == 'SAP'

    @ddt.data(
        {
            'default_locale': None,
            'expected_locale': u'English'
        },
        {
            'default_locale': u'Spanish',
            'expected_locale': u'Spanish'
        },
    )
    @ddt.unpack
    def test_locales_wo_additional_locales(self, default_locale, expected_locale):
        """
        Verify that ``SAPSuccessFactorsEnterpriseCustomerConfiguration.get_locales`` works without additional_locales
        """
        assert self.config.additional_locales == ''
        assert self.config.get_locales(default_locale) == set([expected_locale])

    def test_locales_w_additional_locales(self):
        """
        Verify that ``SAPSuccessFactorsEnterpriseCustomerConfiguration.get_locales`` works with additional_locales
        """
        self.config.additional_locales = 'Malay,     Arabic,English United Kingdom,   '
        self.config.save()

        assert self.config.get_locales() == set(['English', 'Malay', 'Arabic', 'English United Kingdom'])


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorsGlobalConfiguration(unittest.TestCase):
    """
    Tests of the SAPSuccessFactorsGlobalConfiguration model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``SAPSuccessFactorsGlobalConfiguration`` conversion to string
        """
        config = factories.SAPSuccessFactorsGlobalConfigurationFactory(id=1)
        expected_to_str = "<SAPSuccessFactorsGlobalConfiguration with id 1>"
        assert expected_to_str == method(config)


@mark.django_db
@ddt.ddt
class TestDegreedLearnerDataTransmissionAudit(unittest.TestCase):
    """
    Tests of the ``DegreedLearnerDataTransmissionAudit`` model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``DegreedLearnerDataTransmissionAudit`` conversion to string
        """
        learner_audit = factories.DegreedLearnerDataTransmissionAuditFactory(
            id=1,
            enterprise_course_enrollment_id=5,
            degreed_user_email='degreed_user_email',
            course_id='course-v1:edX+DemoX+DemoCourse',
        )
        expected_to_str = (
            "<DegreedLearnerDataTransmissionAudit 1 for enterprise enrollment 5, email degreed_user_email, "
            "and course course-v1:edX+DemoX+DemoCourse>"
        )
        assert expected_to_str == method(learner_audit)


@mark.django_db
@ddt.ddt
class TestDegreedEnterpriseCustomerConfiguration(unittest.TestCase):
    """
    Tests of the DegreedEnterpriseCustomerConfiguration model.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
        )
        super(TestDegreedEnterpriseCustomerConfiguration, self).setUp()

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``DegreedEnterpriseCustomerConfiguration`` conversion to string
        """
        assert method(self.config) == "<DegreedEnterpriseCustomerConfiguration for Enterprise GriffCo>"

    def test_channel_code(self):
        assert self.config.channel_code() == 'DEGREED'


@mark.django_db
@ddt.ddt
class TestDegreedGlobalConfiguration(unittest.TestCase):
    """
    Tests of the ``DegreedGlobalConfiguration`` model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``DegreedGlobalConfiguration`` conversion to string
        """
        config = factories.DegreedGlobalConfigurationFactory(id=1)
        expected_to_str = "<DegreedGlobalConfiguration with id 1>"
        assert expected_to_str == method(config)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerReportingConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerReportingConfiguration model.
    """

    @ddt.data(str, repr)
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerReportingConfiguration`` conversion to string
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        config = EnterpriseCustomerReportingConfiguration(
            enterprise_customer=enterprise_customer,
            active=True,
            delivery_method=EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_EMAIL,
            email='test@edx.org',
            frequency=EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_MONTHLY,
            day_of_month=1,
            hour_of_day=1,
        )

        expected_to_str = "<EnterpriseCustomerReportingConfiguration for Enterprise {}>".format(
            enterprise_customer.name
        )
        assert expected_to_str == method(config)

    @ddt.data(
        (EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_DAILY, 1, 1, None, None, None),
        (EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_WEEKLY, 1, 1, None, 1, None),
        (EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_WEEKLY, None, None, None, None,
         ['Day of week must be set if the frequency is weekly.']),
        (EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_MONTHLY, 1, 1, 1, None, None),
        (EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_MONTHLY, None, None, None, None,
         ['Day of month must be set if the frequency is monthly.']),
        ('invalid_frequency', None, None, None, None,
         ['Frequency must be set to either daily, weekly, or monthly.']),
    )
    @ddt.unpack
    def test_clean_frequency_fields(
            self,
            frequency,
            day_of_month,
            day_of_week,
            expected_day_of_month,
            expected_day_of_week,
            expected_error,
    ):
        """
        Test ``EnterpriseCustomerReportingConfiguration`` custom clean function validating frequency related fields.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        config = EnterpriseCustomerReportingConfiguration(
            enterprise_customer=enterprise_customer,
            active=True,
            delivery_method=EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_EMAIL,
            email='test@edx.org',
            decrypted_password='test_password',
            frequency=frequency,
            day_of_month=day_of_month,
            day_of_week=day_of_week,
            hour_of_day=1,
        )

        if expected_error:
            try:
                config.clean()
            except ValidationError as validation_error:
                assert validation_error.messages == expected_error
        else:
            config.clean()

        assert config.day_of_month == expected_day_of_month
        assert config.day_of_week == expected_day_of_week

    def test_clean_missing_sftp_fields(self):
        """
        Test ``EnterpriseCustomerReportingConfiguration`` custom clean function validating sftp related fields.
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        config = EnterpriseCustomerReportingConfiguration(
            enterprise_customer=enterprise_customer,
            active=True,
            delivery_method=EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_SFTP,
            email='test@edx.org',
            frequency=EnterpriseCustomerReportingConfiguration.FREQUENCY_TYPE_DAILY,
            hour_of_day=1,
        )

        expected_errors = [
            'SFTP Hostname must be set if the delivery method is sftp.',
            'SFTP File Path must be set if the delivery method is sftp.',
            'SFTP username must be set if the delivery method is sftp.',
            'Decrypted SFTP password must be set if the delivery method is SFTP.',
        ]
        try:
            config.clean()
        except ValidationError as validation_error:
            assert sorted(validation_error.messages) == sorted(expected_errors)


@mark.django_db
@ddt.ddt
class TestSystemWideEnterpriseUserRoleAssignment(unittest.TestCase):
    """
    Tests SystemWideEnterpriseUserRoleAssignment.
    """

    @ddt.data(
        {
            'role_name': ENTERPRISE_LEARNER_ROLE,
            'expected_context': ['47130371-0b6d-43f5-01de-71942664de2b'],
        },
        {
            'role_name': ENTERPRISE_OPERATOR_ROLE,
            'expected_context': ['*'],
        }
    )
    @ddt.unpack
    def test_get_context(self, role_name, expected_context):
        """
        Verify that `SystemWideEnterpriseUserRoleAssignment.get_context` method works as expected.
        """
        user_email = 'edx@example.com'
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid='47130371-0b6d-43f5-01de-71942664de2b')
        user = factories.UserFactory(email=user_email)
        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)

        enterprise_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=role_name)
        enterprise_role_assignment, __ = SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
            user=user,
            role=enterprise_role
        )

        assert enterprise_role_assignment.get_context() == expected_context

    @ddt.data(
        {
            'role_name': ENTERPRISE_LEARNER_ROLE,
            'expected_context': [u'47130371-0b6d-43f5-01de-71942664de2c', u'47130371-0b6d-43f5-01de-71942664de2b'],
        },
        {
            'role_name': ENTERPRISE_OPERATOR_ROLE,
            'expected_context': ['*'],
        }
    )
    @ddt.unpack
    def test_get_context_for_multiple_contexts(self, role_name, expected_context):
        """
        Verify that `SystemWideEnterpriseUserRoleAssignment.get_context` method works as expected for user with
        multiple contexts.
        """
        user_email = 'edx@example.com'
        enterprise_customer_1 = factories.EnterpriseCustomerFactory(uuid='47130371-0b6d-43f5-01de-71942664de2b')
        enterprise_customer_2 = factories.EnterpriseCustomerFactory(uuid='47130371-0b6d-43f5-01de-71942664de2c')
        user = factories.UserFactory(email=user_email)
        EnterpriseCustomerUser.objects.link_user(enterprise_customer_1, user_email)
        EnterpriseCustomerUser.objects.link_user(enterprise_customer_2, user_email)

        enterprise_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=role_name)
        enterprise_role_assignment, __ = SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
            user=user,
            role=enterprise_role
        )

        assert enterprise_role_assignment.get_context() == expected_context


@mark.django_db
@ddt.ddt
class TestEnterpriseCatalogQuery(unittest.TestCase):
    """
    Tests for the EnterpriseCatalogQuery model.
    """

    @ddt.data(
        {
            'content_filter': {'key': 'coursev1:course1'},
            'error': ["Content filter 'key' must be of type <class 'list'>"]
        },
        {
            'content_filter': {'first_enrollable_paid_seat_price__lte': [12]},
            'error': ["Content filter 'first_enrollable_paid_seat_price__lte' must be of type <class 'str'>"]
        },
        {
            'content_filter': {'key': [3, 'course']},
            'error': ["Content filter 'key' must contain values of type <class 'str'>"]
        }
    )
    @ddt.unpack
    def test_save_content_filter_fail(self, content_filter, error):
        catalog_query = EnterpriseCatalogQuery(content_filter=content_filter)
        try:
            catalog_query.full_clean()
        except ValidationError as validation_error:
            assert sorted(validation_error.messages) == sorted(error)

    @ddt.data(
        {
            'content_filter': {'key': ['coursev1:course1', ]},
        },
        {
            'content_filter': {'aggregation_key': ['courserun:course', ]},
        },
        {
            'content_filter': {'first_enrollable_paid_seat_price__lte': "12"},
        }
    )
    @ddt.unpack
    def test_save_content_filter_success(self, content_filter):
        catalog_query = EnterpriseCatalogQuery(content_filter=content_filter)
        catalog_query.full_clean()

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_sync_catalog_query_content_filter(self, mock_api_client):  # pylint: disable=unused-argument
        enterprise_customer = factories.EnterpriseCustomerFactory()
        catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            sync_enterprise_catalog_query=True,
            enterprise_catalog_query=None,
            content_filter={'key': 'course-v-one-million:course123'},
        )
        catalog.save()
        expected_content_filter = {'key': 'course-v-one-million:course123'}
        assert expected_content_filter == catalog.content_filter

        catalog.enterprise_catalog_query = factories.EnterpriseCatalogQueryFactory(
            content_filter={'key': 'coursev1:course1'}
        )
        catalog.save()
        expected_content_filter = {'key': 'coursev1:course1'}
        assert expected_content_filter == catalog.content_filter

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    def test_no_sync_of_catalog_query_content_filter(self, mock_api_client):  # pylint: disable=unused-argument
        enterprise_customer = factories.EnterpriseCustomerFactory()
        enterprise_catalog_query = factories.EnterpriseCatalogQueryFactory(
            content_filter={'key': 'coursev1:course1'},
        )
        catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            sync_enterprise_catalog_query=False,
            enterprise_catalog_query=enterprise_catalog_query,
            content_filter={'key': 'course-v-one-million:course123'},
        )
        catalog.save()
        expected_content_filter = {'key': 'course-v-one-million:course123'}
        assert expected_content_filter == catalog.content_filter
