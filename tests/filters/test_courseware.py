"""
Tests for enterprise.filters.courseware pipeline steps.
"""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import ddt
import pytest
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseStartDateValidationFailed, CoursewareAccessChecksRequested

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from enterprise.filters.courseware import ActiveEnterpriseCheckStep, EnterpriseStartDateAccessFailureStep
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)


@ddt.ddt
class TestEnterpriseStartDateAccessFailureStep(TestCase):
    """Tests for EnterpriseStartDateAccessFailureStep."""

    def _make_step(self):
        return EnterpriseStartDateAccessFailureStep(
            "org.openedx.learning.course.start_date.validation_failed.v1", []
        )

    @ddt.data(
        # Enterprise learner with a specific start date: raises with formatted date in messages.
        {
            "is_authenticated": True,
            "has_request": True,
            "enterprise_learner_enrolled": True,
            "start_date": datetime(2026, 9, 1, tzinfo=ZoneInfo("UTC")),
            "expected_raises_error_code": "course_not_started_enterprise_learner",
            "expected_raises_developer_message": "2026-09-01",
            "expected_raises_user_message": "Course does not start until September 01, 2026",
        },
        # Enterprise learner with the default/unscheduled start date: raises with generic "has not started" messages.
        {
            "is_authenticated": True,
            "has_request": True,
            "enterprise_learner_enrolled": True,
            "start_date": datetime(2040, 1, 1, tzinfo=ZoneInfo("UTC")),
            "expected_raises_error_code": "course_not_started_enterprise_learner",
            "expected_raises_developer_message": (
                "Course has not started, and the learner is enrolled via an enterprise subsidy."
            ),
            "expected_raises_user_message": "Course has not started",
        },
        # Authenticated user who is not an enterprise learner: passes through.
        {
            "is_authenticated": True,
            "has_request": True,
            "enterprise_learner_enrolled": False,
            "start_date": datetime(2026, 9, 1, tzinfo=ZoneInfo("UTC")),
            "expected_raises_error_code": None,
            "expected_raises_developer_message": None,
            "expected_raises_user_message": None,
        },
        # Unauthenticated user: passes through without calling enterprise_learner_enrolled.
        {
            "is_authenticated": False,
            "has_request": True,
            "enterprise_learner_enrolled": False,
            "start_date": datetime(2026, 9, 1, tzinfo=ZoneInfo("UTC")),
            "expected_raises_error_code": None,
            "expected_raises_developer_message": None,
            "expected_raises_user_message": None,
        },
        # No CRUM request available: passes through without calling enterprise_learner_enrolled.
        {
            "is_authenticated": True,
            "has_request": False,
            "enterprise_learner_enrolled": False,
            "start_date": datetime(2026, 9, 1, tzinfo=ZoneInfo("UTC")),
            "expected_raises_error_code": None,
            "expected_raises_developer_message": None,
            "expected_raises_user_message": None,
        },
    )
    @ddt.unpack
    @patch('enterprise.filters.courseware.enterprise_learner_enrolled')
    @patch('enterprise.filters.courseware.get_current_request')
    def test_run_filter(
        self,
        mock_get_request,
        mock_enrolled,
        is_authenticated,
        has_request,
        enterprise_learner_enrolled,
        start_date,
        expected_raises_error_code,
        expected_raises_developer_message,
        expected_raises_user_message,
    ):
        """Raises OverrideStartDateError for enterprise learners; passes through otherwise."""
        if has_request:
            request = RequestFactory().get('/')
            request.user = UserFactory.create() if is_authenticated else AnonymousUser()
            mock_get_request.return_value = request
        else:
            mock_get_request.return_value = None
        mock_enrolled.return_value = enterprise_learner_enrolled

        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        step = self._make_step()
        if expected_raises_error_code:
            with pytest.raises(CourseStartDateValidationFailed.OverrideStartDateError) as exc_info:
                step.run_filter(course_key=course_key, start_date=start_date)
            assert exc_info.value.error_code == expected_raises_error_code
            assert expected_raises_developer_message in exc_info.value.developer_message
            assert exc_info.value.user_message == expected_raises_user_message
        else:
            result = step.run_filter(course_key=course_key, start_date=start_date)
            assert result == {"course_key": course_key, "start_date": start_date}


class TestActiveEnterpriseCheckStep(TestCase):
    """Tests for ActiveEnterpriseCheckStep."""

    def _make_step(self):
        return ActiveEnterpriseCheckStep(
            "org.openedx.learning.courseware.access_checks.requested.v1", [],
        )

    def test_no_enterprise_enrollments_passthrough(self):
        """When the user has no enterprise enrollments, the step is a no-op."""
        user = UserFactory.create()
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key)
        assert result == {"user": user, "course_key": course_key}

    def test_matching_active_customer_passthrough(self):
        """When the active EnterpriseCustomerUser matches the enrollment's customer, no exception."""
        user = UserFactory.create()
        ec = EnterpriseCustomerFactory()
        ecu = EnterpriseCustomerUserFactory(enterprise_customer=ec, user_id=user.id, active=True)
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        EnterpriseCourseEnrollmentFactory(enterprise_customer_user=ecu, course_id=str(course_key))
        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key)
        assert result == {"user": user, "course_key": course_key}

    def test_mismatched_active_customer_raises(self):
        """When the active EnterpriseCustomerUser does not match, PreventCoursewareAccess is raised."""
        user = UserFactory.create()
        enrolled_ec = EnterpriseCustomerFactory(name="EnrolledCo")
        active_ec = EnterpriseCustomerFactory(name="ActiveCo")
        enrolled_ecu = EnterpriseCustomerUserFactory(
            enterprise_customer=enrolled_ec, user_id=user.id, active=False,
        )
        EnterpriseCustomerUserFactory(enterprise_customer=active_ec, user_id=user.id, active=True)
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        EnterpriseCourseEnrollmentFactory(enterprise_customer_user=enrolled_ecu, course_id=str(course_key))
        step = self._make_step()
        with pytest.raises(CoursewareAccessChecksRequested.PreventCoursewareAccess) as exc_info:
            step.run_filter(user=user, course_key=course_key)
        assert exc_info.value.error_code == "incorrect_active_enterprise"
        assert "EnrolledCo" in exc_info.value.user_message
        assert "ActiveCo" in exc_info.value.user_message
