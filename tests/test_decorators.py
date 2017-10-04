# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` decorators.
"""
from __future__ import absolute_import, unicode_literals

import unittest
import warnings
from importlib import import_module

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory

from enterprise.decorators import (
    deprecated,
    disable_for_loaddata,
    enterprise_login_required,
    force_fresh_session,
    ignore_warning,
)
from enterprise.django_compatibility import reverse
from six.moves.urllib.parse import parse_qs, unquote, urlparse  # pylint: disable=import-error
from test_utils import get_magic_name, mock_view_function
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory


@ddt.ddt
@mark.django_db
class TestEnterpriseDecorators(unittest.TestCase):
    """
    Tests for enterprise decorators.
    """
    def setUp(self):
        """
        Set up test environment.
        """
        super(TestEnterpriseDecorators, self).setUp()
        faker = FakerFactory.create()
        self.provider_id = faker.slug()  # pylint: disable=no-member
        self.uuid = faker.uuid4()  # pylint: disable=no-member
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=self.customer)
        self.session_engine = import_module(settings.SESSION_ENGINE)

    def _prepare_request(self, url, user):
        """
        Prepare request for test.
        """
        request = RequestFactory().get(url)
        request.user = user
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        request.session = self.session_engine.SessionStore(session_key)
        return request

    def test_deprecated(self):
        """
        Calling a deprecated function emits a warning.
        """
        def func():
            """ Function to be decorated. """
            pass
        with warnings.catch_warnings(record=True) as warning:
            warnings.simplefilter('always')
            deprecated('Yep!')(func)()
            assert len(warning) is 1
            assert issubclass(warning[0].category, DeprecationWarning)
            assert str(warning[0].message) == 'You called the deprecated function `func`. Yep!'

    def test_ignore_warning(self):
        """
        Emitted warnings from a function are ignored.
        """
        def func():
            """ Function to be decorated. """
            pass
        with warnings.catch_warnings(record=True) as warning:
            warnings.simplefilter('always')
            ignore_warning(DeprecationWarning)(func)()
            deprecated('Yep!')(func)()
            assert len(warning) is 0

    @ddt.data(True, False)
    def test_disable_for_loaddata(self, raw):
        signal_handler_mock = mock.MagicMock()
        signal_handler_mock.__name__ = get_magic_name("Irrelevant")
        wrapped_handler = disable_for_loaddata(signal_handler_mock)

        wrapped_handler(raw=raw)

        assert signal_handler_mock.called != raw

    @ddt.data(
        {},  # Missing required parameter `enterprise_uuid` arguments in kwargs
        {'enterprise_uuid': ''},  # Required parameter `enterprise_uuid` with empty value in kwargs.
        # pylint: disable=no-member
        {'enterprise_uuid': FakerFactory.create().uuid4()},  # Invalid value of `enterprise_uuid` in kwargs.
    )
    def test_enterprise_login_required_raises_404(self, kwargs):
        """
        Test that the decorator `enterprise_login_required` raises `Http404`
        error when called with invalid or missing arguments.
        """
        view_function = mock_view_function()
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, 'course-v1:edX+DemoX+Demo_Course'],
        )
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        with raises(Http404):
            enterprise_login_required(view_function)(request, **kwargs)

    def test_enterprise_login_required_redirects_for_anonymous_users(self):
        """
        Test that the decorator `enterprise_login_required` returns Http
        Redirect for anonymous users.
        """
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = self._prepare_request(enterprise_launch_url, AnonymousUser())

        response = enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when an anonymous
        # user tries to access enterprise course enrollment page.
        assert response.status_code == 302
        assert 'new_enterprise_login%3Dyes' in response.url
        assert 'tpa_hint' in response.url

    def test_enterprise_login_required(self):
        """
        Test that the enterprise login decorator calls the view function.

        Test that the decorator `enterprise_login_required` calls the view
        function when:
            1. `enterprise_uuid` is provided and corresponding enterprise
                customer exists in database.
            2. User making the request is authenticated.

        """
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    def test_force_fresh_session_anonymous_user(self):
        """
        Test that the force_fresh_session decorator calls the
        decorated view the request is made by an unauthenticated
        user.
        """
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = self._prepare_request(enterprise_launch_url, AnonymousUser())

        force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called and the session flag was set.
        assert view_function.called

    @mock.patch('enterprise.decorators.get_identity_provider')
    def test_force_fresh_session_no_sso_provider(self, mock_get_idp):  # pylint: disable=unused-argument
        """
        Test that the force_fresh_session decorator calls the view function
        when no sso provider is configured.
        """
        mock_get_idp.return_value = None
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    def test_force_fresh_session_param_received(self):
        """
        Test that the force_fresh_session decorator calls the view function
        if the session is fresh.
        """
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        enterprise_launch_url += '?new_enterprise_login=yes'
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @ddt.data(True, False)
    @mock.patch('enterprise.utils.Registry')
    def test_force_fresh_session_param_not_received(self, drop_exisiting_session, mock_registry):
        """
        Test that the force_fresh_session decorator redirects authenticated
        users with the appropriate provider config depending on the IdPs configuration.
        """
        mock_registry.get.return_value.configure_mock(
            provider_id=self.provider_id,
            drop_existing_session=drop_exisiting_session
        )
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        url_path = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        query = 'foo=bar'
        # Adding query parameter here to verify
        # the redirect URL is getting escaped properly.
        url = '{path}?{query}'.format(path=url_path, query=query)
        request = self._prepare_request(url, UserFactory(is_active=True))

        response = force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        if drop_exisiting_session:
            # Assert that redirect status code 302 is returned when a logged in user comes in
            # with an sso provider configured to drop existing sessions
            assert response.status_code == 302
            # Assert the redirect URL query string is intact.
            redirect_url_query = parse_qs(urlparse(response.url).query)
            assert urlparse(unquote(redirect_url_query['redirect_url'][0])).query == query
        else:
            # Assert that view function was called.
            assert view_function.called
