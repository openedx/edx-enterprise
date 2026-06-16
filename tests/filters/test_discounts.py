"""
Tests for enterprise.filters.discounts pipeline step.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from enterprise.filters.discounts import DiscountEligibilityEnterpriseStep


class _FakeDiscountIneligible(Exception):
    pass


class _FakeDiscountEligibilityCheckRequested:
    DiscountIneligible = _FakeDiscountIneligible


class TestDiscountEligibilityEnterpriseStep(TestCase):
    """
    Tests for DiscountEligibilityEnterpriseStep pipeline step.
    """

    def _make_step(self):
        return DiscountEligibilityEnterpriseStep(
            "org.openedx.learning.discount.eligibility.check.requested.v1",
            [],
        )

    def _mock_user(self):
        user = MagicMock()
        user.id = 42
        return user

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=True)
    @patch('enterprise.filters.discounts.DiscountEligibilityCheckRequested', _FakeDiscountEligibilityCheckRequested)
    def test_raises_discount_ineligible_for_enterprise_learner(self, mock_is_enterprise):
        """
        When the user is an enterprise learner, DiscountIneligible is raised to halt the pipeline.
        """
        user = self._mock_user()
        course_key = MagicMock()

        step = self._make_step()
        with self.assertRaises(_FakeDiscountIneligible):
            step.run_filter(user=user, course_key=course_key, is_eligible=True)

        mock_is_enterprise.assert_called_once_with(user)

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=False)
    def test_returns_original_eligibility_for_non_enterprise_learner(self, _mock_is_enterprise):
        """
        When the user is not an enterprise learner, is_eligible is passed through unchanged.
        """
        user = self._mock_user()
        course_key = MagicMock()

        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key, is_eligible=True)

        self.assertEqual(result, {"user": user, "course_key": course_key, "is_eligible": True})

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=False)
    def test_passes_through_false_eligibility_unchanged(self, _mock_is_enterprise):
        """
        When the user is not an enterprise learner and is_eligible is already False,
        the step does not change it.
        """
        user = self._mock_user()
        course_key = MagicMock()

        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key, is_eligible=False)

        self.assertEqual(result["is_eligible"], False)

    @patch('enterprise.filters.discounts.is_enterprise_learner', return_value=False)
    def test_course_key_passed_through_unchanged(self, _):
        """
        The course_key is returned unchanged for non-enterprise learners.
        """
        user = self._mock_user()
        course_key = MagicMock()

        step = self._make_step()
        result = step.run_filter(user=user, course_key=course_key, is_eligible=True)

        self.assertIs(result["course_key"], course_key)
