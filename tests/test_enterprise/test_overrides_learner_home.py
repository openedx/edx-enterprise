"""
Tests for enterprise.overrides.learner_home pluggable override.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from enterprise.overrides.learner_home import enterprise_get_enterprise_customer


class TestEnterpriseGetEnterpriseCustomer(TestCase):
    """
    Tests for enterprise_get_enterprise_customer override function.
    """

    @patch('enterprise.overrides.learner_home.enterprise_customer_from_session_or_learner_data')
    @patch('enterprise.overrides.learner_home.get_enterprise_learner_data_from_db')
    def test_non_masquerading_delegates_to_session_api(
        self,
        mock_get_enterprise_learner_data_from_db,
        mock_enterprise_customer_from_session_or_learner_data,
    ):
        """
        When is_masquerading is False, should call
        enterprise_customer_from_session_or_learner_data(request) and return its result.
        """
        request = MagicMock()
        user = MagicMock()
        expected = {'uuid': 'test-uuid'}
        mock_enterprise_customer_from_session_or_learner_data.return_value = expected
        mock_get_enterprise_learner_data_from_db.return_value = []

        result = enterprise_get_enterprise_customer(MagicMock(), user, request, is_masquerading=False)

        mock_enterprise_customer_from_session_or_learner_data.assert_called_once_with(request)
        mock_get_enterprise_learner_data_from_db.assert_not_called()
        self.assertEqual(result, expected)

    @patch('enterprise.overrides.learner_home.enterprise_customer_from_session_or_learner_data')
    @patch('enterprise.overrides.learner_home.get_enterprise_learner_data_from_db')
    def test_masquerading_returns_enterprise_customer_from_db(
        self,
        mock_get_enterprise_learner_data_from_db,
        mock_enterprise_customer_from_session_or_learner_data,
    ):
        """
        When is_masquerading is True and learner data exists, should return the
        enterprise_customer from the first learner data entry.
        """
        user = MagicMock()
        request = MagicMock()
        enterprise_customer = {'uuid': 'ec-uuid', 'name': 'Test Enterprise'}
        mock_get_enterprise_learner_data_from_db.return_value = [
            {'enterprise_customer': enterprise_customer}
        ]

        result = enterprise_get_enterprise_customer(MagicMock(), user, request, is_masquerading=True)

        mock_get_enterprise_learner_data_from_db.assert_called_once_with(user)
        mock_enterprise_customer_from_session_or_learner_data.assert_not_called()
        self.assertEqual(result, enterprise_customer)

    @patch('enterprise.overrides.learner_home.enterprise_customer_from_session_or_learner_data')
    @patch('enterprise.overrides.learner_home.get_enterprise_learner_data_from_db')
    def test_masquerading_returns_none_when_no_learner_data(
        self,
        mock_get_enterprise_learner_data_from_db,
        mock_enterprise_customer_from_session_or_learner_data,
    ):
        """
        When is_masquerading is True but no learner data exists, should return None.
        """
        user = MagicMock()
        request = MagicMock()
        mock_get_enterprise_learner_data_from_db.return_value = []

        result = enterprise_get_enterprise_customer(MagicMock(), user, request, is_masquerading=True)

        mock_get_enterprise_learner_data_from_db.assert_called_once_with(user)
        mock_enterprise_customer_from_session_or_learner_data.assert_not_called()
        self.assertIsNone(result)
