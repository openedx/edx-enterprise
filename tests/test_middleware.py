"""
Tests for enterprise middleware.
"""

import unittest
from unittest import mock

import ddt
from pytest import mark

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import Client, RequestFactory

from enterprise.middleware import EnterpriseLanguagePreferenceMiddleware
from test_utils.factories import (
    AnonymousUserFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

LANGUAGE_KEY = 'pref-lang'
UserAPIInternalError = Exception
UserAPIRequestError = Exception


@mark.django_db
@ddt.ddt
class TestUserPreferenceMiddleware(unittest.TestCase):
    """
    Tests to make sure language configured by the `default_language` column on EnterpriseCustomer is being used.
    """

    def setUp(self):
        """
        Setup middleware, request, session, user and enterprise customer for tests. Also mock imports from edx-platform.
        """
        self.mock_imports()

        super().setUp()
        self.mock_response = mock.Mock()
        self.middleware = EnterpriseLanguagePreferenceMiddleware(self.mock_response)
        self.session_middleware = SessionMiddleware(self.mock_response)
        self.user = UserFactory.create()
        self.anonymous_user = AnonymousUserFactory()
        self.request = RequestFactory().get('/somewhere')
        self.request.user = self.user
        self.request.META['HTTP_ACCEPT_LANGUAGE'] = 'ar;q=1.0'
        self.session_middleware.process_request(self.request)
        self.client = Client()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

    def mock_imports(self):
        """
        Mock all the imports from edx-platform
        """
        mocks = [
            mock.patch('enterprise.middleware.LANGUAGE_KEY', LANGUAGE_KEY),
            mock.patch('enterprise.middleware.UserAPIInternalError', UserAPIInternalError),
            mock.patch('enterprise.middleware.UserAPIRequestError', UserAPIRequestError),
            mock.patch('enterprise.middleware.get_user_preference', mock.MagicMock(return_value=None)),
            mock.patch('enterprise.middleware.is_request_from_mobile_app', mock.MagicMock(return_value=False)),
            mock.patch('enterprise.utils.UserPreference', mock.MagicMock()),

        ]
        for mock_object in mocks:
            self.jwt_builder = mock_object.start()
            self.addCleanup(mock_object.stop)

    @ddt.data(None, 'es', 'en')
    def test_preference_setting_changes_cookie(self, lang_pref_out):
        """
        Validate that the language set via enterprise customer's `default_language`
        column is used as the learner's default language.
        """
        self.enterprise_customer.default_language = lang_pref_out
        self.enterprise_customer.save()
        self.middleware.process_request(self.request)

        assert getattr(self.request, '_anonymous_user_cookie_lang', None) == lang_pref_out

    def test_real_user_extracted_from_request(self):
        """
        Validate the the real_user is used in cases where user is masquerading as someone else.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = UserFactory()
        self.request.user.real_user = self.user

        self.middleware.process_request(self.request)

        # Make sure the real user is used for setting the language cookie
        assert getattr(self.request, '_anonymous_user_cookie_lang', None) == self.enterprise_customer.default_language

    def test_cookie_not_set_for_anonymous_user(self):
        """
        Validate the language cookie is not set if the request user is not authenticated.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = self.anonymous_user
        self.middleware.process_request(self.request)

        # Make sure the set cookie is not called for anonymous users
        assert getattr(self.request, '_anonymous_user_cookie_lang', None) is None

    def test_cookie_not_set_for_non_enterprise_learners(self):
        """
        Validate the language cookie is not set if the request user does not belong to any enterprise customer.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = UserFactory()
        self.middleware.process_request(self.request)

        # Make sure the set cookie is not called for anonymous users
        assert getattr(self.request, '_anonymous_user_cookie_lang', None) is None

    def test_cookie_when_there_is_no_request_user(self):
        """
        Validate the language cookie is not set if, for some reason, the request user is not present.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        request = RequestFactory().get('/somewhere')
        self.mock_response = mock.Mock()
        session_middleware = SessionMiddleware(self.mock_response)
        session_middleware.process_request(request)

        self.middleware.process_request(request)

        # Make sure the set cookie is not called for anonymous users
        assert getattr(self.request, '_anonymous_user_cookie_lang', None) is None

    def test_errors_are_handled(self):
        """
        Validate that the errors raised when querying user preference are handled correctly.
        In this case those errors are ignored.
        """
        with mock.patch('enterprise.middleware.get_user_preference') as mock_get_user_preference:
            mock_get_user_preference.side_effect = UserAPIInternalError
            self.middleware.process_request(self.request)

            # Make sure the set cookie is not called for anonymous users
            # pylint: disable=protected-access,no-member
            assert self.request._anonymous_user_cookie_lang == self.enterprise_customer.default_language

    def test_cookie_not_set_for_mobile_requests(self):
        """
        Validate the language cookie is not set if the request is coming from the mobile app.
        """
        with mock.patch('enterprise.middleware.is_request_from_mobile_app') as mock_is_request_from_mobile_app:
            mock_is_request_from_mobile_app.return_value = True
            self.middleware.process_request(self.request)

            # Make sure the set cookie is not called for anonymous users
            assert getattr(self.request, '_anonymous_user_cookie_lang', None) is None

    def test_middleware_when_cookie_lang_is_different_from_user_pref(self):
        """
        Validate that when user pref and cookie language are set but have different values
        then the middleware updates the cookie with user preference value.
        """
        user_pref_lang = 'ar'
        cookie_lang = 'en'
        self.request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = cookie_lang

        with mock.patch('enterprise.middleware.get_user_preference') as mock_get_user_preference:
            mock_get_user_preference.return_value = user_pref_lang
            self.middleware.process_request(self.request)

            assert self.request.COOKIES[settings.LANGUAGE_COOKIE_NAME] == user_pref_lang
            assert getattr(self.request, '_anonymous_user_cookie_lang', None) == user_pref_lang
