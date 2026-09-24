"""
Tests for the enterprise.overrides.program_nudge_email pluggable override.
"""
import unittest
from unittest.mock import MagicMock, patch

import ddt

from django.test import override_settings

from enterprise.overrides.program_nudge_email import enterprise_suggested_course_url

PORTAL_BASE_URL = 'https://portal.example.com'
DEFAULT_URL = 'https://www.example.com/course/edx-demo'
SUGGESTED_COURSE = {'key': 'edX+DemoX', 'title': 'Demo Course'}
SUGGESTED_COURSE_RUN = {'key': 'course-v1:edX+DemoX+2026', 'marketing_url': 'course/edx-demo'}


def _learner_data(enable_learner_portal, slug='test-org'):
    """
    Build what ``get_enterprise_learner_data_from_db`` returns for a linked learner.
    """
    return [{
        'enterprise_customer': {
            'name': 'Test Org',
            'slug': slug,
            'enable_learner_portal': enable_learner_portal,
        },
    }]


@ddt.ddt
class TestEnterpriseSuggestedCourseUrl(unittest.TestCase):
    """
    Tests for the enterprise_suggested_course_url override function.
    """

    @ddt.data(
        # A portal-enabled customer sends the learner to the B2B course landing page.
        {
            'learner_data': _learner_data(enable_learner_portal=True),
            'expected_url': 'https://portal.example.com/test-org/course/edX+DemoX',
            'delegates': False,
        },
        # A linked learner whose customer has no learner portal delegates to the platform.
        {
            'learner_data': _learner_data(enable_learner_portal=False),
            'expected_url': DEFAULT_URL,
            'delegates': True,
        },
        # A learner linked to no enterprise customer at all delegates to the platform.
        {
            'learner_data': [],
            'expected_url': DEFAULT_URL,
            'delegates': True,
        },
        # get_enterprise_learner_data_from_db returns None for an unauthenticated user: delegate, do not raise.
        {
            'learner_data': None,
            'expected_url': DEFAULT_URL,
            'delegates': True,
        },
    )
    @ddt.unpack
    @override_settings(ENTERPRISE_LEARNER_PORTAL_BASE_URL=PORTAL_BASE_URL)
    @patch('enterprise.overrides.program_nudge_email.get_enterprise_learner_data_from_db')
    def test_suggested_course_url(self, mock_learner_data, learner_data, expected_url, delegates):
        mock_learner_data.return_value = learner_data
        user = MagicMock()
        prev_fn = MagicMock(return_value=DEFAULT_URL)

        result = enterprise_suggested_course_url(
            prev_fn,
            user=user,
            suggested_course=SUGGESTED_COURSE,
            suggested_course_run=SUGGESTED_COURSE_RUN,
        )

        assert result == expected_url
        mock_learner_data.assert_called_once_with(user)
        if delegates:
            prev_fn.assert_called_once_with(
                user=user,
                suggested_course=SUGGESTED_COURSE,
                suggested_course_run=SUGGESTED_COURSE_RUN,
            )
        else:
            prev_fn.assert_not_called()
