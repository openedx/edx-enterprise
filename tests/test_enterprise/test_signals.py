# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from opaque_keys.edx.keys import CourseKey
from pytest import mark

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from enterprise.signals import handle_user_post_save
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnrollmentFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)


@mark.django_db
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
        handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1

    @mock.patch('enterprise.api_client.lms.CourseEnrollment')
    def test_handle_user_post_save_with_pending_course_enrollment(self, mock_course_enrollment):
        mock_course_enrollment.enroll.return_value = None
        email = "fake_email@edx.org"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        PendingEnrollmentFactory(user=pending_link, course_id=course_id)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"
        assert PendingEnrollment.objects.filter(user=pending_link).count() == 1, \
            'Precondition check: only one enrollment exists.'

        parameters = {'instance': user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1
        assert PendingEnrollment.objects.count() == 0
        assert EnterpriseCourseEnrollment.objects.count() == 1
        mock_course_enrollment.enroll.assert_called_once_with(
            user, CourseKey.from_string(course_id), mode='audit', check_access=True
        )

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
        # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
        assert link.id == existing_link.id, "Should keep existing link intact"  # pylint: disable=no-member
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
