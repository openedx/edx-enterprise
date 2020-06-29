# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

import unittest

import ddt
import mock
from pytest import mark

from django.db import transaction
from django.test import override_settings

from enterprise.constants import ENTERPRISE_LEARNER_ROLE
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.signals import create_enterprise_enrollment_receiver, handle_user_post_save
from test_utils.factories import (
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnrollmentFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)


@mark.django_db(transaction=True)
@ddt.ddt
class TestUserPostSaveSignalHandler(unittest.TestCase):
    """
    Test User post_save signal handler.
    """

    def test_handle_user_post_save_no_user_instance_nothing_happens(self):
        # precondition checks
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

        parameters = {"instance": None, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

    def test_handle_user_post_save_no_matching_pending_link(self):
        user = UserFactory(email="jackie.chan@hollywood.com")

        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending links available"
        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no links exists"

        parameters = {"instance": user, "created": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

    def test_handle_user_post_save_created_user(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": True}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1

    def test_handle_user_post_save_modified_user_not_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1

    @mock.patch('enterprise.utils.track_event')
    @mock.patch('enterprise.signals.track_enrollment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    def test_handle_user_post_save_with_pending_course_enrollment(
            self,
            mock_course_enrollment,
            mock_track_enrollment,
            mock_track_event  # pylint: disable=unused-argument
    ):
        mock_course_enrollment.enroll.return_value = None
        email = "fake_email@edx.org"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        pending_link.enterprise_customer.enable_autocohorting = True
        pending_link.enterprise_customer.save()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        PendingEnrollmentFactory(user=pending_link, course_id=course_id, cohort_name=u'test_cohort')

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"
        assert PendingEnrollment.objects.filter(user=pending_link).count() == 1, \
            'Precondition check: only one enrollment exists.'

        mock_course_enrollment.return_value = mock.Mock(
            get_course_enrollment=mock.Mock(
                side_effect=[None, {'is_active': False, 'mode': 'verified'}]
            ),
            enroll_user_in_course=mock.Mock()
        )
        parameters = {'instance': user, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1
        assert PendingEnrollment.objects.count() == 0
        assert EnterpriseCourseEnrollment.objects.count() == 1
        mock_course_enrollment.return_value.enroll_user_in_course.assert_called_once_with(
            user.username, course_id, 'audit', cohort=u'test_cohort'
        )
        mock_track_enrollment.assert_called_once_with('pending-admin-enrollment', user.id, course_id)

    def test_handle_user_post_save_modified_user_already_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        enterprise_customer1, enterprise_customer2 = EnterpriseCustomerFactory(), EnterpriseCustomerFactory()
        existing_link = EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user.id)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1, "Precondition check: links exists"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        link = EnterpriseCustomerUser.objects.get(user_id=user.id)
        assert link.id == existing_link.id, "Should keep existing link intact"
        assert link.enterprise_customer == enterprise_customer1, "Should keep existing link intact"

        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Should delete pending link"

    def test_handle_user_post_save_raw(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False, "raw": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Link have been created"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Pending link should be kept"


@mark.django_db
@ddt.ddt
class TestDefaultContentFilter(unittest.TestCase):
    """
    Tests for the content_filter field of the EnterpriseCustomerCatalog model.
    """

    @ddt.data(
        (
            {
                'content_type': 'course',
                'partner': 'edx'
            },
            {
                'content_type': 'course',
                'partner': 'edx'
            }
        ),
        (
            {
                'content_type': 'course',
                'level_type': [
                    'Introductory',
                    'Intermediate'
                ],
                'availability': [
                    'Current',
                    'Starting Soon',
                    'Upcoming'
                ],
                'status': 'published'
            },
            {
                'content_type': 'course',
                'level_type': [
                    'Introductory',
                    'Intermediate'
                ],
                'availability': [
                    'Current',
                    'Starting Soon',
                    'Upcoming'
                ],
                'status': 'published'
            }
        ),
        # if the value is not set is settings, it picks default value from constant.
        (
            {},
            {'content_type': 'course'}
        )
    )
    @ddt.unpack
    @mock.patch('enterprise.utils.DEFAULT_CATALOG_CONTENT_FILTER', {'content_type': 'course'})
    def test_default_content_filter(self, default_content_filter, expected_content_filter):
        """
        Test that `EnterpriseCustomerCatalog`.content_filter is saved with correct default content filter.
        """
        with override_settings(ENTERPRISE_CUSTOMER_CATALOG_DEFAULT_CONTENT_FILTER=default_content_filter):
            enterprise_catalog = EnterpriseCustomerCatalogFactory()
            assert enterprise_catalog.content_filter == expected_content_filter


@mark.django_db
@ddt.ddt
class TestEnterpriseLearnerRoleSignals(unittest.TestCase):
    """
    Tests signals associated with EnterpriseCustomerUser.
    """
    def setUp(self):
        """
        Setup for `TestEnterpriseLearnerRoleSignals` test.
        """
        self.enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        self.learner_user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        super(TestEnterpriseLearnerRoleSignals, self).setUp()

    def test_assign_enterprise_learner_role_success(self):
        """
        Test that when a new `EnterpriseCustomerUser` record is created, `assign_enterprise_learner_role` assigns an
        enterprise learner role to it.
        """
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that now a new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertTrue(learner_role_assignment.exists())

    @ddt.data(
        (True, False),
        (False, True),
    )
    @ddt.unpack
    def test_enterprise_learner_role_post_save(self, should_unlink_user, should_learner_role_exist):
        """
        Verify enterprise_learner role is assigned on the EnterpriseCustomerUser
        create operation and that the enterprise_learner role is deleted on the
        EnterpriseCustomerUser update operation when the `linked` attribute is False.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )

        modified_datetime_at_create = learner_role_assignment.modified

        # Update EnterpriseCustomerUser record.
        enterprise_customer_user = EnterpriseCustomerUser.objects.get(
            user_id=self.learner_user.id
        )
        if should_unlink_user:
            enterprise_customer_user.linked = False
        else:
            enterprise_customer_user.active = False
        enterprise_customer_user.save()

        if should_learner_role_exist:
            # Verify that learner_role_assignment is not modified again when making a
            # normal update, i.e. modified time is the same as when the object was created.
            learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(
                user=self.learner_user,
                role=self.enterprise_learner_role
            )
            self.assertEqual(learner_role_assignment.modified, modified_datetime_at_create)
        else:
            # Verify that the enterprise_learner role is deleted when unlinking an EnterpriseCustomerUser
            learner_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.learner_user,
                role=self.enterprise_learner_role
            )
            self.assertFalse(learner_role_assignments.exists())

    def test_assign_enterprise_learner_role_no_user_association(self):
        """
        Test that `assign_enterprise_learner_role` does not do anything if no User object is not associated with
        `EnterpriseCustomerUser` record.
        """
        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Create a new EnterpriseCustomerUser with no user associated.
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )

        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_success(self):
        """
        Test that when `EnterpriseCustomerUser` record is deleted, `delete_enterprise_learner_role_assignment` also
        deletes the enterprise learner role assignment associated with it.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that now a new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertTrue(learner_role_assignment.exists())

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that learner role assignment is deleted as well.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_no_role_assignment(self):
        """
        Test that when if no role assignment is associated with a deleted `EnterpriseCustomerUser` record,
        `delete_enterprise_learner_role_assignment` does nothing.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Delete the role assignment record for tesing purposes.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        learner_role_assignment.delete()

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that no new learner role assignment is created hence won't be deleted.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_no_user_associated(self):
        """
        Test that when if no user is associated with a deleted `EnterpriseCustomerUser` record,
        `delete_enterprise_learner_role_assignment` does nothing.
        """
        # Create a new EnterpriseCustomerUser with no user associated.
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=self.enterprise_customer
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that no new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=self.enterprise_customer
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that no new learner role assignment is created hence won't be deleted.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())


@mark.django_db
class TestCourseEnrollmentSignals(unittest.TestCase):
    """
    Tests signals associated with CourseEnrollments (that are found in edx-platform).
    """
    def setUp(self):
        """
        Setup for `TestCourseEnrollmentSignals` test.
        """
        self.user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.non_enterprise_user = UserFactory(id=999, email='user999@example.com')
        super(TestCourseEnrollmentSignals, self).setUp()

    @mock.patch('enterprise.tasks.create_enterprise_enrollment.delay')
    def test_receiver_calls_task_if_ecu_exists(self, mock_task):
        """
        Receiver should call a task
        if user tied to the CourseEnrollment that is handed into the function
        is an EnterpriseCustomerUser
        """
        sender = mock.Mock()  # This would be a CourseEnrollment class
        instance = mock.Mock()  # This would be a CourseEnrollment instance
        instance.user = self.user
        instance.course_id = "fake:course_id"
        # Signal metadata (note: 'signal' would be an actual object, but we dont need it here)
        kwargs = {
            'update_fields': None,
            'raw': False,
            'signal': '<django.db.models.signals.ModelSignal object at 0x7fcfc38b5e90>',
            'using': 'default',
            'created': True,
        }

        create_enterprise_enrollment_receiver(sender, instance, **kwargs)
        mock_task.assert_called_once_with(str(instance.course_id), self.enterprise_customer_user.id)

    @mock.patch('enterprise.tasks.create_enterprise_enrollment.delay')
    def test_receiver_does_not_call_task_if_ecu_not_exists(self, mock_task):
        """
        Receiver should NOT call a task
        if user tied to the CourseEnrollment that is handed into the function
        is NOT an EnterpriseCustomerUser
        """
        sender = mock.Mock()  # This would be a CourseEnrollment class
        instance = mock.Mock()  # This would be a CourseEnrollment instance
        instance.user = self.non_enterprise_user
        instance.course_id = "fake:course_id"
        # Signal metadata (note: 'signal' would be an actual object, but we dont need it here)
        kwargs = {
            'update_fields': None,
            'raw': False,
            'signal': '<django.db.models.signals.ModelSignal object at 0x7fcfc38b5e90>',
            'using': 'default',
            'created': True,
        }

        create_enterprise_enrollment_receiver(sender, instance, **kwargs)
        mock_task.assert_not_called()


@mark.django_db
class TestEnterpriseCatalogSignals(unittest.TestCase):
    """
    Tests the EnterpriseCustomerCatalogAdmin
    """

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_delete_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        enterprise_catalog_uuid = enterprise_catalog.uuid
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        enterprise_catalog.delete()

        # Verify the API was called correctly and the catalog was deleted
        api_client_mock.return_value.delete_enterprise_catalog.assert_called_with(enterprise_catalog_uuid)
        self.assertFalse(EnterpriseCustomerCatalog.objects.exists())

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_create_catalog(self, api_client_mock):
        api_client_mock.return_value.get_enterprise_catalog.return_value = {}
        enterprise_catalog = EnterpriseCustomerCatalogFactory()

        # Verify the API was called and the catalog "was created" (even though it already was)
        # This method is a little weird in that the object is sort of created / not-created at the same time
        api_client_mock.return_value.create_enterprise_catalog.assert_called_with(
            str(enterprise_catalog.uuid),
            str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_catalog.enterprise_customer.name,
            enterprise_catalog.title,
            enterprise_catalog.content_filter,
            enterprise_catalog.enabled_course_modes,
            enterprise_catalog.publish_audit_enrollment_urls
        )

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_update_catalog_without_existing_service_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        api_client_mock.return_value.get_enterprise_catalog.return_value = {}

        enterprise_catalog.title = 'New title'
        enterprise_catalog.save()

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.create_enterprise_catalog.assert_called_with(
            str(enterprise_catalog.uuid),
            str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_catalog.enterprise_customer.name,
            enterprise_catalog.title,
            enterprise_catalog.content_filter,
            enterprise_catalog.enabled_course_modes,
            enterprise_catalog.publish_audit_enrollment_urls
        )

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_update_catalog_with_existing_service_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        api_client_mock.return_value.get_enterprise_catalog.return_value = True

        enterprise_catalog.title = 'New title'
        enterprise_catalog.save()

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.update_enterprise_catalog.assert_called_with(
            enterprise_catalog.uuid,
            enterprise_customer=str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_customer_name=enterprise_catalog.enterprise_customer.name,
            title=enterprise_catalog.title,
            content_filter=enterprise_catalog.content_filter,
            enabled_course_modes=enterprise_catalog.enabled_course_modes,
            publish_audit_enrollment_urls=enterprise_catalog.publish_audit_enrollment_urls
        )
