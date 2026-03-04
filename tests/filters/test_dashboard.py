"""
Tests for enterprise.filters.dashboard pipeline step.
"""
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from enterprise.filters.dashboard import DashboardContextEnricher


FILTER_TYPE = "org.openedx.learning.dashboard.render.started.v1"

# Patch targets — names are bound in enterprise.filters.dashboard at import time.
_CONSENT_PATH = 'enterprise.filters.dashboard.get_dashboard_consent_notification'
_PORTAL_PATH = 'enterprise.filters.dashboard.get_enterprise_learner_portal_context'
_IS_ENTERPRISE_PATH = 'enterprise.filters.dashboard.is_enterprise_learner'


class TestDashboardContextEnricher(TestCase):
    """
    Tests for DashboardContextEnricher pipeline step.
    """

    def _make_step(self):
        return DashboardContextEnricher(FILTER_TYPE, [])

    def _make_request(self):
        factory = RequestFactory()
        return factory.get('/')

    def _make_user(self):
        user = MagicMock()
        user.id = 42
        return user

    @patch(_IS_ENTERPRISE_PATH, return_value=True)
    @patch(
        _PORTAL_PATH,
        return_value={'enterprise_portal_url': 'https://portal.example.com'},
    )
    @patch(_CONSENT_PATH, return_value='You must consent.')
    def test_enriches_context_for_enterprise_learner(
        self, mock_consent, mock_portal, mock_is_enterprise
    ):
        """
        For an enterprise learner, the step injects enterprise_message, is_enterprise_user,
        and enterprise portal keys into the dashboard context.
        """
        request = self._make_request()
        user = self._make_user()
        enrollments = [MagicMock()]
        context = {
            'request': request,
            'user': user,
            'course_enrollment_pairs': enrollments,
        }
        template_name = 'student/dashboard.html'

        step = self._make_step()
        result = step.run_filter(context=context, template_name=template_name)

        assert result['template_name'] == template_name
        result_context = result['context']
        assert result_context['enterprise_message'] == 'You must consent.'
        assert result_context['is_enterprise_user'] is True
        assert result_context['enterprise_portal_url'] == 'https://portal.example.com'

        mock_consent.assert_called_once_with(request, user, enrollments)
        mock_portal.assert_called_once_with(request)
        mock_is_enterprise.assert_called_once_with(user)

    @patch(_IS_ENTERPRISE_PATH, return_value=False)
    @patch(_PORTAL_PATH, return_value={})
    @patch(_CONSENT_PATH, return_value='')
    def test_enriches_context_for_non_enterprise_learner(
        self, mock_consent, mock_portal, mock_is_enterprise
    ):
        """
        For a non-enterprise learner, is_enterprise_user is False and enterprise_message is empty.
        """
        request = self._make_request()
        user = self._make_user()
        context = {
            'request': request,
            'user': user,
        }
        template_name = 'student/dashboard.html'

        step = self._make_step()
        result = step.run_filter(context=context, template_name=template_name)

        result_context = result['context']
        assert result_context['enterprise_message'] == ''
        assert result_context['is_enterprise_user'] is False

    def test_returns_unchanged_context_when_no_user(self):
        """
        When no user is present in context, the step returns context unchanged without calling
        any enterprise helper functions.
        """
        context = {'request': MagicMock()}
        template_name = 'student/dashboard.html'

        step = self._make_step()
        result = step.run_filter(context=context, template_name=template_name)

        assert result == {'context': context, 'template_name': template_name}
        assert 'enterprise_message' not in result['context']
        assert 'is_enterprise_user' not in result['context']

    @patch(_IS_ENTERPRISE_PATH, return_value=True)
    @patch(_PORTAL_PATH, side_effect=Exception('portal error'))
    @patch(_CONSENT_PATH, side_effect=Exception('consent error'))
    def test_handles_exceptions_gracefully(
        self, mock_consent, mock_portal, mock_is_enterprise
    ):
        """
        When enterprise helper functions raise exceptions, the step logs warnings and continues
        with fallback values, not propagating the exception.
        """
        request = self._make_request()
        user = self._make_user()
        context = {
            'request': request,
            'user': user,
        }
        template_name = 'student/dashboard.html'

        step = self._make_step()
        # Should not raise
        result = step.run_filter(context=context, template_name=template_name)

        result_context = result['context']
        assert result_context['enterprise_message'] == ''
        assert 'is_enterprise_user' in result_context

    @patch(_IS_ENTERPRISE_PATH, return_value=True)
    @patch(
        _PORTAL_PATH,
        return_value={'enterprise_portal_url': 'https://portal.example.com'},
    )
    @patch(_CONSENT_PATH, return_value='')
    def test_uses_empty_list_when_course_enrollment_pairs_missing(
        self, mock_consent, mock_portal, mock_is_enterprise
    ):
        """
        When course_enrollment_pairs is not in context, an empty list is passed to
        get_dashboard_consent_notification.
        """
        request = self._make_request()
        user = self._make_user()
        context = {
            'request': request,
            'user': user,
            # no 'course_enrollment_pairs' key
        }
        template_name = 'student/dashboard.html'

        step = self._make_step()
        step.run_filter(context=context, template_name=template_name)

        mock_consent.assert_called_once_with(request, user, [])
