"""
Tests for the `edx-enterprise` decorators.
"""

import unittest
import warnings
from importlib import import_module
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

import ddt
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse

from enterprise.decorators import (
    deprecated,
    disable_for_loaddata,
    enterprise_login_required,
    force_fresh_session,
    ignore_warning,
)
from test_utils import get_magic_name, mock_view_function
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory

FAKER = FakerFactory.create()


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
        super().setUp()
        self.provider_id = FAKER.slug()  # pylint: disable=no-member
        self.uuid = FAKER.uuid4()  # pylint: disable=no-member
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        self.identity_provider = EnterpriseCustomerIdentityProviderFactory(
            provider_id=self.provider_id,
            enterprise_customer=self.customer
        )
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

        with warnings.catch_warnings(record=True) as warning:
            warnings.simplefilter('always')
            deprecated('Yep!')(func)()
            assert len(warning) == 1
            assert issubclass(warning[0].category, DeprecationWarning)
            assert str(warning[0].message) == 'You called the deprecated function `func`. Yep!'

    def test_ignore_warning(self):
        """
        Emitted warnings from a function are ignored.
        """

        def func():
            """ Function to be decorated. """

        with warnings.catch_warnings(record=True) as warning:
            warnings.simplefilter('always')
            ignore_warning(DeprecationWarning)(func)()
            deprecated('Yep!')(func)()
            assert len(warning) == 0

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
        {'enterprise_uuid': FAKER.uuid4()},  # Invalid value of `enterprise_uuid` in kwargs.
    )
    def test_enterprise_login_required_raises_404(self, kwargs):
        """
        Test that the decorator `enterprise_login_required` raises `Http404`
        error when called with invalid or missing arguments.
        """
        view_function = mock_view_function()
        enterprise_launch_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[self.customer.uuid, 'course-v1:edX+DemoX+Demo_Course'],
        )
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        with raises(Http404):
            enterprise_login_required(view_function)(request, **kwargs)

    @ddt.data(
        ('idp-1', 'idp-1', True, 'idp-1'),
        (None, 'idp-1', True, 'idp-1'),
        ('fake_idp', 'idp-1', True, None),
        ('idp-1', 'idp-1', False, None),
        (None, None, False, None),
    )
    @ddt.unpack
    def test_enterprise_login_required_redirects_for_anonymous_users(
            self,
            tpa_hint_param,
            identity_provided_id,
            link_identity_provider,
            redirected_tpa_hint
    ):
        """
        Test that the decorator `enterprise_login_required` returns Http
        Redirect for anonymous users.
        """
        enterprise_customer = EnterpriseCustomerFactory(uuid=FAKER.uuid4())  # pylint: disable=no-member
        identity_provider = EnterpriseCustomerIdentityProviderFactory()

        if identity_provided_id:
            identity_provider.provider_id = identity_provided_id
            identity_provider.save()

        if link_identity_provider:
            identity_provider.enterprise_customer = enterprise_customer
            identity_provider.save()

        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        if tpa_hint_param:
            enterprise_launch_url = f'{enterprise_launch_url}?tpa_hint={tpa_hint_param}'

        request = self._prepare_request(enterprise_launch_url, AnonymousUser())
        response = enterprise_login_required(view_function)(
            request, enterprise_uuid=enterprise_customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when an anonymous
        # user tries to access enterprise course enrollment page.
        assert response.status_code == 302
        assert 'new_enterprise_login%3Dyes' in response.url
        if redirected_tpa_hint:
            assert f'tpa_hint%3D{redirected_tpa_hint}' in response.url
        else:
            assert f'tpa_hint%3D{redirected_tpa_hint}' not in response.url

    def test_enterprise_login_required_redirects_for_anonymous_users_with_querystring(self):
        """
        Test that the decorator `enterprise_login_required` returns Http
        Redirect for anonymous users while keeping the format of query
        parameters unchanged.
        """
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_enrollment_url = reverse(
            'enterprise_course_run_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        querystring = 'catalog=dummy-catalog-uuid'
        course_enrollment_url = '{course_enrollment_url}?{querystring}'.format(
            course_enrollment_url=course_enrollment_url, querystring=querystring
        )
        request = self._prepare_request(course_enrollment_url, AnonymousUser())

        response = enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when an anonymous
        # user tries to access enterprise course enrollment page.
        assert response.status_code == 302

        # Now verify that the query parameters in the querystring of next url
        # are unchanged
        next_url = parse_qs(urlparse(response.url).query)['next'][0]
        next_url_querystring = unquote(urlparse(next_url).query)
        assert 'new_enterprise_login=yes' in next_url_querystring
        assert 'tpa_hint' in next_url_querystring
        assert querystring in next_url_querystring

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
            'enterprise_course_run_enrollment_page',
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
            'enterprise_course_run_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = self._prepare_request(enterprise_launch_url, AnonymousUser())

        force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called and the session flag was set.
        assert view_function.called

    @mock.patch('enterprise.decorators.get_identity_provider')
    def test_force_fresh_session_no_sso_provider(self, mock_get_idp):
        """
        Test that the force_fresh_session decorator calls the view function
        when no sso provider is configured.
        """
        mock_get_idp.return_value = None
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_launch_url = reverse(
            'enterprise_course_run_enrollment_page',
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
            'enterprise_course_run_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        enterprise_launch_url += '?new_enterprise_login=yes'
        request = self._prepare_request(enterprise_launch_url, UserFactory(is_active=True))

        force_fresh_session(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @mock.patch('enterprise.decorators.get_identity_provider')
    def test_force_fresh_session_param_not_received(self, mock_get_identity_provider):
        """
        Test that the force_fresh_session decorator redirects authenticated
        users with the appropriate provider config depending on the IdPs configuration.
        """
        mock_get_identity_provider.return_value.configure_mock(
            provider_id=self.provider_id,
        )
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        url_path = reverse(
            'enterprise_course_run_enrollment_page',
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

        # Assert that redirect status code 302 is returned
        assert response.status_code == 302
        # Assert the redirect URL query string is intact.
        redirect_url_query = parse_qs(urlparse(response.url).query)
        assert urlparse(unquote(redirect_url_query['redirect_url'][0])).query == query
