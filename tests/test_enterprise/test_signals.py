# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from pytest import mark

from django.db import transaction

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
