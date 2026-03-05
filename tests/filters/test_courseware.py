"""
Tests for enterprise.filters.courseware pipeline steps.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from enterprise.filters.courseware import ConsentRedirectStep, LearnerPortalRedirectStep


class TestConsentRedirectStep(TestCase):
    """Tests for ConsentRedirectStep."""

    def _make_step(self):
        return ConsentRedirectStep(
            "org.openedx.learning.courseware.view.redirect_url.requested.v1", []
        )

    @patch('enterprise.filters.courseware.get_enterprise_consent_url', return_value='/consent/')
    def test_appends_consent_url_when_required(self, mock_get_url):
        """Consent URL is appended when get_enterprise_consent_url returns a URL."""
        step = self._make_step()
        request = MagicMock()
        course_key = MagicMock()
        course_key.__str__ = lambda s: 'course-v1:org+course+run'
        result = step.run_filter(redirect_urls=[], request=request, course_key=course_key)
        self.assertEqual(result['redirect_urls'], ['/consent/'])

    @patch('enterprise.filters.courseware.get_enterprise_consent_url', return_value=None)
    def test_does_not_append_when_no_consent_required(self, mock_get_url):
        """redirect_urls is unchanged when consent is not required."""
        step = self._make_step()
        request = MagicMock()
        course_key = MagicMock()
        course_key.__str__ = lambda s: 'course-v1:org+course+run'
        result = step.run_filter(redirect_urls=[], request=request, course_key=course_key)
        self.assertEqual(result['redirect_urls'], [])


class TestLearnerPortalRedirectStep(TestCase):
    """Tests for LearnerPortalRedirectStep."""

    def _make_step(self):
        return LearnerPortalRedirectStep(
            "org.openedx.learning.courseware.view.redirect_url.requested.v1", []
        )

    @patch('enterprise.filters.courseware.EnterpriseCustomerUser.objects')
    @patch(
        'enterprise.filters.courseware.enterprise_customer_from_session_or_learner_data',
        return_value={'uuid': 'abc-123', 'learner_portal_url': '/portal/'},
    )
    def test_appends_portal_url_for_enrolled_learner(self, mock_customer, mock_ecu_objects):
        """Portal URL is appended when learner is enrolled via enterprise portal."""
        mock_ecu_objects.filter.return_value.exists.return_value = True
        step = self._make_step()
        request = MagicMock()
        request.user.id = 42
        result = step.run_filter(redirect_urls=[], request=request, course_key=MagicMock())
        self.assertEqual(result['redirect_urls'], ['/portal/'])

    @patch(
        'enterprise.filters.courseware.enterprise_customer_from_session_or_learner_data',
        return_value=None,
    )
    def test_does_not_append_when_no_enterprise_customer(self, mock_customer):
        """redirect_urls is unchanged when user has no enterprise customer."""
        step = self._make_step()
        request = MagicMock()
        result = step.run_filter(redirect_urls=[], request=request, course_key=MagicMock())
        self.assertEqual(result['redirect_urls'], [])
