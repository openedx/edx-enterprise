"""
Tests for enterprise.overrides.course_home_progress pluggable override.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch


ENTERPRISE_SUPPORT_UTILS_PATH = 'openedx.features.enterprise_support.utils'


class TestEnterpriseObfuscatedUsername(TestCase):
    """
    Tests for enterprise_obfuscated_username override function.
    """

    def _call(self, request=None, student=None):
        """Import and call the override function."""
        # pylint: disable=import-outside-toplevel
        from enterprise.overrides.course_home_progress import enterprise_obfuscated_username
        prev_fn = MagicMock()
        return enterprise_obfuscated_username(prev_fn, request, student)

    def test_enterprise_learner_returns_generic_name(self):
        """
        When get_enterprise_learner_generic_name returns a non-empty string,
        should return that string.
        """
        request = MagicMock()
        student = MagicMock()
        expected_name = 'Enterprise Learner'
        mock_utils = MagicMock()
        mock_utils.get_enterprise_learner_generic_name.return_value = expected_name

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_UTILS_PATH: mock_utils}):
            result = self._call(request=request, student=student)

        mock_utils.get_enterprise_learner_generic_name.assert_called_once_with(request)
        self.assertEqual(result, expected_name)

    def test_non_enterprise_learner_returns_none(self):
        """
        When get_enterprise_learner_generic_name returns None (no enterprise generic name),
        should return None.
        """
        request = MagicMock()
        student = MagicMock()
        mock_utils = MagicMock()
        mock_utils.get_enterprise_learner_generic_name.return_value = None

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_UTILS_PATH: mock_utils}):
            result = self._call(request=request, student=student)

        mock_utils.get_enterprise_learner_generic_name.assert_called_once_with(request)
        self.assertIsNone(result)

    def test_empty_string_generic_name_returns_none(self):
        """
        When get_enterprise_learner_generic_name returns an empty string,
        should return None (falsy value is converted to None via `or None`).
        """
        request = MagicMock()
        student = MagicMock()
        mock_utils = MagicMock()
        mock_utils.get_enterprise_learner_generic_name.return_value = ''

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_UTILS_PATH: mock_utils}):
            result = self._call(request=request, student=student)

        mock_utils.get_enterprise_learner_generic_name.assert_called_once_with(request)
        self.assertIsNone(result)

    def test_prev_fn_is_not_called(self):
        """
        The override fully replaces the default implementation — prev_fn should not be called.
        """
        request = MagicMock()
        student = MagicMock()
        prev_fn = MagicMock()
        mock_utils = MagicMock()
        mock_utils.get_enterprise_learner_generic_name.return_value = 'Some Name'

        # pylint: disable=import-outside-toplevel
        from enterprise.overrides.course_home_progress import enterprise_obfuscated_username
        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_UTILS_PATH: mock_utils}):
            enterprise_obfuscated_username(prev_fn, request, student)

        prev_fn.assert_not_called()
