"""
Tests for enterprise middleware.
"""

import unittest

import ddt
import mock
from pytest import mark

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test.client import Client, RequestFactory
from django.utils.translation import LANGUAGE_SESSION_KEY

from enterprise.middleware import EnterpriseLanguagePreferenceMiddleware
from test_utils.factories import (
    AnonymousUserFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

COOKIE_DURATION = 14 * 24 * 60 * 60  # 14 days in seconds
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
        super(TestUserPreferenceMiddleware, self).setUp()
        self.middleware = EnterpriseLanguagePreferenceMiddleware()
        self.session_middleware = SessionMiddleware()
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
        self.mock_imports()

    def mock_imports(self):
        """
        Mock all the imports from edx-platform
        """
        mocks = [
            mock.patch('enterprise.middleware.COOKIE_DURATION', COOKIE_DURATION),
            mock.patch('enterprise.middleware.LANGUAGE_KEY', LANGUAGE_KEY),
            mock.patch('enterprise.middleware.UserAPIInternalError', UserAPIInternalError),
            mock.patch('enterprise.middleware.UserAPIRequestError', UserAPIRequestError),
            mock.patch('enterprise.middleware.get_user_preference', mock.MagicMock(return_value=None)),
            mock.patch('enterprise.middleware.is_request_from_mobile_app', mock.MagicMock(return_value=False)),

        ]
        for mock_object in mocks:
            self.jwt_builder = mock_object.start()
            self.addCleanup(mock_object.stop)

    def test_logout_should_not_remove_cookie(self):
        """
        Validate that the cookie is not removed if the learner logs out.
        """
        self.request.user = self.anonymous_user

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(self.request, response)

        response.delete_cookie.assert_not_called()

    @ddt.data(None, 'es', 'en')
    def test_preference_setting_changes_cookie(self, lang_pref_out):
        """
        Validate that the language set via enterprise customer's `default_language`
        column is used as the learner's default language.
        """
        self.enterprise_customer.default_language = lang_pref_out
        self.enterprise_customer.save()

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(self.request, response)

        if lang_pref_out:
            response.set_cookie.assert_called_with(
                settings.LANGUAGE_COOKIE,
                value=lang_pref_out,
                domain=settings.SESSION_COOKIE_DOMAIN,
                max_age=COOKIE_DURATION,
                secure=self.request.is_secure(),
            )
        else:
            response.set_cookie.assert_not_called()

        self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)

    def test_real_user_extracted_from_request(self):
        """
        Validate the the real_user is used in cases where user is masquerading as someone else.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = UserFactory()
        self.request.user.real_user = self.user

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(self.request, response)

        # Make sure the real user is used for setting the language cookie
        response.set_cookie.assert_called_with(
            settings.LANGUAGE_COOKIE,
            value=self.enterprise_customer.default_language,
            domain=settings.SESSION_COOKIE_DOMAIN,
            max_age=COOKIE_DURATION,
            secure=self.request.is_secure(),
        )

        self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)

    def test_cookie_not_set_for_anonymous_user(self):
        """
        Validate the language cookie is not set if the request user is not authenticated.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = self.anonymous_user

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(self.request, response)

        # Make sure the set cookie is not called for anonymous users
        response.set_cookie.assert_not_called()
        self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)

    def test_cookie_not_set_for_non_enterprise_learners(self):
        """
        Validate the language cookie is not set if the request user does not belong to any enterprise customer.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        self.request.user = UserFactory()

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(self.request, response)

        # Make sure the set cookie is not called for anonymous users
        response.set_cookie.assert_not_called()
        self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)

    def test_cookie_when_there_is_no_request_user(self):
        """
        Validate the language cookie is not set if, for some reason, the request user is not present.
        """
        # Hide the real user and masquerade as a fake user, fake user does not belong to any enterprise customer.
        request = RequestFactory().get('/somewhere')
        session_middleware = SessionMiddleware()
        session_middleware.process_request(request)

        response = mock.Mock(spec=HttpResponse)
        self.middleware.process_response(request, response)

        # Make sure the set cookie is not called for anonymous users
        response.set_cookie.assert_not_called()
        self.assertNotIn(LANGUAGE_SESSION_KEY, request.session)

    def test_errors_are_handled(self):
        """
        Validate that the errors raised when querying user preference are handled correctly.
        In this case those errors are ignored.
        """
        with mock.patch('enterprise.middleware.get_user_preference') as mock_get_user_preference:
            mock_get_user_preference.side_effect = UserAPIInternalError
            response = mock.Mock(spec=HttpResponse)
            self.middleware.process_response(self.request, response)

            # Make sure the set cookie is not called for anonymous users
            response.set_cookie.assert_called_with(
                settings.LANGUAGE_COOKIE,
                value=self.enterprise_customer.default_language,
                domain=settings.SESSION_COOKIE_DOMAIN,
                max_age=COOKIE_DURATION,
                secure=self.request.is_secure(),
            )
            self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)

    def test_cookie_not_set_for_mobile_requests(self):
        """
        Validate the language cookie is not set if the request is coming from the mobile app.
        """
        with mock.patch('enterprise.middleware.is_request_from_mobile_app') as mock_is_request_from_mobile_app:
            mock_is_request_from_mobile_app.return_value = True
            response = mock.Mock(spec=HttpResponse)
            self.middleware.process_response(self.request, response)

            # Make sure the set cookie is not called for anonymous users
            response.set_cookie.assert_not_called()
            self.assertNotIn(LANGUAGE_SESSION_KEY, self.request.session)
