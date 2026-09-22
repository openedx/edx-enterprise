"""
Tests for the enterprise.overrides.branding pluggable overrides.
"""
import unittest
from unittest.mock import MagicMock, patch

import ddt

from django.test import override_settings

from enterprise.overrides.branding import enterprise_learner_generic_name, enterprise_learner_portal_link

PORTAL_BASE_URL = 'https://portal.example.com'
PORTAL_DATA = {
    'name': 'Test Org',
    'slug': 'test-org',
    'logo': 'https://logos.example.com/test-org.png',
}
PORTAL_LINK = {
    'url': 'https://portal.example.com/test-org',
    'logo': 'https://logos.example.com/test-org.png',
    'name': 'Test Org',
}
DELEGATED_NAME = 'real_username'
DELEGATED_LINK = {
    'url': 'https://previous.example.com/portal',
    'logo': 'https://previous.example.com/logo.png',
    'name': 'Previous Implementation',
}


@ddt.ddt
class TestEnterpriseLearnerGenericName(unittest.TestCase):
    """
    Tests for the enterprise_learner_generic_name override function.

    The override takes no request argument; it reads the current one from crum, which is
    patched here because these are plain calls that never pass through middleware.
    ``prev_fn`` returns DELEGATED_NAME, so that is the expected result of any case which
    must delegate to the platform.
    """

    @ddt.data(
        # A customer with a configured generic name hides the learner's username.
        {
            'has_request': True,
            'enterprise_generic_name': 'Test OrgLearner',
            'expected_result': 'Test OrgLearner',
        },
        # The platform helper returns '' for a learner with no customer, or a customer that
        # does not replace sensitive SSO usernames. That must delegate, not blank the name.
        {
            'has_request': True,
            'enterprise_generic_name': '',
            'expected_result': DELEGATED_NAME,
        },
        # The platform helper returns None on 404 pages, which must also delegate.
        {
            'has_request': True,
            'enterprise_generic_name': None,
            'expected_result': DELEGATED_NAME,
        },
        # crum only holds a request during a request cycle. Outside one -- a management
        # command, a celery task, a shell -- it returns None, which must delegate rather
        # than be handed to the platform helper. The helper is armed with a name it would
        # win with, so consulting it at all would change the result.
        {
            'has_request': False,
            'enterprise_generic_name': 'Test OrgLearner',
            'expected_result': DELEGATED_NAME,
        },
    )
    @ddt.unpack
    @patch('enterprise.overrides.branding.get_current_request')
    @patch('enterprise.overrides.branding.get_enterprise_learner_generic_name')
    def test_generic_name(
        self,
        mock_generic_name,
        mock_get_current_request,
        has_request,
        enterprise_generic_name,
        expected_result,
    ):
        mock_get_current_request.return_value = MagicMock() if has_request else None
        mock_generic_name.return_value = enterprise_generic_name
        prev_fn = MagicMock(return_value=DELEGATED_NAME)

        result = enterprise_learner_generic_name(prev_fn, user=MagicMock())

        assert result == expected_result


@ddt.ddt
class TestEnterpriseLearnerPortalLink(unittest.TestCase):
    """
    Tests for the enterprise_learner_portal_link override function.

    The override takes no arguments at all; everything it needs comes from crum, which is
    patched here because these are plain calls that never pass through middleware.
    ``prev_fn`` returns DELEGATED_LINK, so that is the expected result of any case which
    must delegate to it. In production the previous implementation is usually the platform
    default, which returns None -- a sentinel link is used here only so that delegating is
    distinguishable from returning None directly.
    """

    @ddt.data(
        # A portal-enabled customer yields an absolute URL built from the base URL and slug.
        {
            'has_request': True,
            'anonymous': False,
            'portal': PORTAL_DATA,
            'expected_result': PORTAL_LINK,
        },
        # A learner with no portal-enabled customer delegates to the platform.
        {
            'has_request': True,
            'anonymous': False,
            'portal': None,
            'expected_result': DELEGATED_LINK,
        },
        # The header renders for anonymous visitors too, so the override must tolerate a
        # request with no authenticated user rather than raising.
        {
            'has_request': True,
            'anonymous': True,
            'portal': None,
            'expected_result': DELEGATED_LINK,
        },
        # crum only holds a request during a request cycle. Outside one -- a management
        # command, a celery task, a shell -- it returns None, which must delegate rather
        # than be handed to the platform helper. The helper is armed with a portal it would
        # build a link from, so consulting it at all would change the result.
        {
            'has_request': False,
            'anonymous': False,
            'portal': PORTAL_DATA,
            'expected_result': DELEGATED_LINK,
        },
    )
    @ddt.unpack
    @override_settings(ENTERPRISE_LEARNER_PORTAL_BASE_URL=PORTAL_BASE_URL)
    @patch('enterprise.overrides.branding.get_current_request')
    @patch('enterprise.overrides.branding.get_enterprise_learner_portal')
    def test_portal_link(
        self,
        mock_portal,
        mock_get_current_request,
        has_request,
        anonymous,
        portal,
        expected_result,
    ):
        request = None
        if has_request:
            request = MagicMock()
            if anonymous:
                request.user.is_authenticated = False
                request.user.id = None
        mock_get_current_request.return_value = request
        mock_portal.return_value = dict(portal) if portal else portal
        prev_fn = MagicMock(return_value=DELEGATED_LINK)

        result = enterprise_learner_portal_link(prev_fn)

        assert result == expected_result
