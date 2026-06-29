"""
Tests for enterprise.overrides.learner_home pluggable override.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch


ENTERPRISE_SUPPORT_API_PATH = 'openedx.features.enterprise_support.api'


class TestEnterpriseGetEnterpriseCustomer(TestCase):
    """
    Tests for enterprise_get_enterprise_customer override function.
    """

    def _call(self, user=None, request=None, is_masquerading=False):
        """Import and call the override function."""
        # pylint: disable=import-outside-toplevel
        from enterprise.overrides.learner_home import enterprise_get_enterprise_customer
        prev_fn = MagicMock()
        return enterprise_get_enterprise_customer(prev_fn, user, request, is_masquerading)

    def test_non_masquerading_delegates_to_session_api(self):
        """
        When is_masquerading is False, should call
        enterprise_customer_from_session_or_learner_data(request) and return its result.
        """
        request = MagicMock()
        user = MagicMock()
        expected = {'uuid': 'test-uuid'}
        mock_api = MagicMock()
        mock_api.enterprise_customer_from_session_or_learner_data.return_value = expected
        mock_api.get_enterprise_learner_data_from_db.return_value = []

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_API_PATH: mock_api}):
            result = self._call(user=user, request=request, is_masquerading=False)

        mock_api.enterprise_customer_from_session_or_learner_data.assert_called_once_with(request)
        mock_api.get_enterprise_learner_data_from_db.assert_not_called()
        self.assertEqual(result, expected)

    def test_masquerading_returns_enterprise_customer_from_db(self):
        """
        When is_masquerading is True and learner data exists, should return the
        enterprise_customer from the first learner data entry.
        """
        user = MagicMock()
        request = MagicMock()
        enterprise_customer = {'uuid': 'ec-uuid', 'name': 'Test Enterprise'}
        mock_api = MagicMock()
        mock_api.get_enterprise_learner_data_from_db.return_value = [
            {'enterprise_customer': enterprise_customer}
        ]

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_API_PATH: mock_api}):
            result = self._call(user=user, request=request, is_masquerading=True)

        mock_api.get_enterprise_learner_data_from_db.assert_called_once_with(user)
        mock_api.enterprise_customer_from_session_or_learner_data.assert_not_called()
        self.assertEqual(result, enterprise_customer)

    def test_masquerading_returns_none_when_no_learner_data(self):
        """
        When is_masquerading is True but no learner data exists, should return None.
        """
        user = MagicMock()
        request = MagicMock()
        mock_api = MagicMock()
        mock_api.get_enterprise_learner_data_from_db.return_value = []

        with patch.dict('sys.modules', {ENTERPRISE_SUPPORT_API_PATH: mock_api}):
            result = self._call(user=user, request=request, is_masquerading=True)

        mock_api.get_enterprise_learner_data_from_db.assert_called_once_with(user)
        mock_api.enterprise_customer_from_session_or_learner_data.assert_not_called()
        self.assertIsNone(result)
