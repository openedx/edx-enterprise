"""
Tests for enterprise.overrides.course_home_progress pluggable override.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from enterprise.overrides.course_home_progress import enterprise_obfuscated_username


class TestEnterpriseObfuscatedUsername(TestCase):
    """
    Tests for enterprise_obfuscated_username override function.
    """

    def _call(self, request=None, student=None):
        """Call the override function."""
        prev_fn = MagicMock()
        return enterprise_obfuscated_username(prev_fn, request, student)

    @patch(
        'enterprise.overrides.course_home_progress.get_enterprise_learner_generic_name',
        return_value='Enterprise Learner',
    )
    def test_enterprise_learner_returns_generic_name(self, mock_fn):
        """
        When get_enterprise_learner_generic_name returns a non-empty string,
        should return that string.
        """
        request = MagicMock()
        student = MagicMock()

        result = self._call(request=request, student=student)

        mock_fn.assert_called_once_with(request)
        self.assertEqual(result, 'Enterprise Learner')

    @patch(
        'enterprise.overrides.course_home_progress.get_enterprise_learner_generic_name',
        return_value=None,
    )
    def test_non_enterprise_learner_returns_none(self, mock_fn):
        """
        When get_enterprise_learner_generic_name returns None (no enterprise generic name),
        should return None.
        """
        request = MagicMock()
        student = MagicMock()

        result = self._call(request=request, student=student)

        mock_fn.assert_called_once_with(request)
        self.assertIsNone(result)

    @patch(
        'enterprise.overrides.course_home_progress.get_enterprise_learner_generic_name',
        return_value='',
    )
    def test_empty_string_generic_name_returns_none(self, mock_fn):
        """
        When get_enterprise_learner_generic_name returns an empty string,
        should return None (falsy value is converted to None via `or None`).
        """
        request = MagicMock()
        student = MagicMock()

        result = self._call(request=request, student=student)

        mock_fn.assert_called_once_with(request)
        self.assertIsNone(result)

    @patch('enterprise.overrides.course_home_progress.get_enterprise_learner_generic_name', None)
    def test_utility_unavailable_delegates_to_prev_fn(self):
        """
        When get_enterprise_learner_generic_name is None (import failed), should
        call and return the result of prev_fn(request, student).
        """
        request = MagicMock()
        student = MagicMock()
        prev_fn = MagicMock(return_value='default-username')

        result = enterprise_obfuscated_username(prev_fn, request, student)

        prev_fn.assert_called_once_with(request, student)
        self.assertEqual(result, 'default-username')

    @patch(
        'enterprise.overrides.course_home_progress.get_enterprise_learner_generic_name',
        return_value='Some Name',
    )
    def test_prev_fn_is_not_called(self, _):
        """
        The override fully replaces the default implementation — prev_fn should not be called.
        """
        request = MagicMock()
        student = MagicMock()
        prev_fn = MagicMock()

        enterprise_obfuscated_username(prev_fn, request, student)

        prev_fn.assert_not_called()
