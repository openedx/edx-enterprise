# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
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
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.all()) == 0

        parameters = {"instance": None, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.all()) == 0

    def test_handle_user_post_save_no_matching_pending_link(self):
        user = UserFactory(email="jackie.chan@hollywood.com")

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no pending links available"
        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no links exists"

        parameters = {"instance": user, "created": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.all()) == 0

    def test_handle_user_post_save_created_user(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0, "Precondition check: no links exists"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        )) == 1

    def test_handle_user_post_save_modified_user_not_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0, "Precondition check: no links exists"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        )) == 1

    @mock.patch('enterprise.lms_api.CourseKey')
    @mock.patch('enterprise.lms_api.CourseEnrollment')
    def test_handle_user_post_save_with_pending_course_enrollment(self, mock_course_enrollment, mock_course_key):
        mock_course_key.from_string.return_value = None
        mock_course_enrollment.enroll.return_value = None
        email = "fake_email@edx.org"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        pending_enrollment = PendingEnrollmentFactory(user=pending_link)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0, "Precondition check: no links exists"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Precondition check: pending link exists"
        assert len(PendingEnrollment.objects.filter(user=pending_link)) == 1, 'Check that only one enrollment exists.'

        parameters = {'instance': user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert len(EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        )) == 1
        assert len(PendingEnrollment.objects.all()) == 0
        assert len(EnterpriseCourseEnrollment.objects.all()) == 1
        mock_course_enrollment.enroll.assert_called_once_with(user, None, mode='audit', check_access=True)
        mock_course_key.from_string.assert_called_once_with(pending_enrollment.course_id)

    def test_handle_user_post_save_modified_user_already_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        enterprise_customer1, enterprise_customer2 = EnterpriseCustomerFactory(), EnterpriseCustomerFactory()
        existing_link = EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user.id)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_email=email)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1, "Precondition check: links exists"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        link = EnterpriseCustomerUser.objects.get(user_id=user.id)
        # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
        assert link.id == existing_link.id, "Should keep existing link intact"  # pylint: disable=no-member
        assert link.enterprise_customer == enterprise_customer1, "Should keep existing link intact"

        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "Should delete pending link"

    def test_handle_user_post_save_raw(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        PendingEnterpriseCustomerUserFactory(user_email=email)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0, "Precondition check: no links exists"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False, "raw": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0, "Link have been created"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1, \
            "Pending link should be kept"
