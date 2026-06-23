"""
Tests for enterprise.filters.discounts pipeline step.
"""
from unittest.mock import patch

from opaque_keys.edx.keys import CourseKey

from django.test import TestCase

from openedx_filters.learning.filters import DiscountEligibilityCheckRequested

from enterprise.filters.discounts import DiscountEligibilityEnterpriseStep
from test_utils.factories import UserFactory


class TestDiscountEligibilityEnterpriseStep(TestCase):
    """
    Tests for DiscountEligibilityEnterpriseStep pipeline step.
    """

    def _make_step(self):
        return DiscountEligibilityEnterpriseStep(
            "org.openedx.learning.discount.eligibility.check.requested.v1",
            [],
        )

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=True)
    def test_raises_discount_ineligible_for_enterprise_learner(self, mock_is_enterprise):
        """
        When the user is an enterprise learner, DiscountIneligible is raised to halt the pipeline.
        """
        user = UserFactory()
        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')

        step = self._make_step()
        with self.assertRaises(DiscountEligibilityCheckRequested.DiscountIneligible):
            step.run_filter(user=user, course_key=course_key)

        mock_is_enterprise.assert_called_once_with(user)

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=False)
    def test_returns_user_and_course_key_for_non_enterprise_learner(self, _mock_is_enterprise):
        """
        When the user is not an enterprise learner, user and course_key are returned unchanged.
        """
        user = UserFactory()
        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')

        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key)

        self.assertEqual(result, {"user": user, "course_key": course_key})

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=False)
    def test_course_key_passed_through_unchanged(self, _):
        """
        The course_key is returned unchanged for non-enterprise learners.
        """
        user = UserFactory()
        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')

        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key)

        self.assertIs(result["course_key"], course_key)
