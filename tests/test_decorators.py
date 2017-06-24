# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` decorators.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory

from enterprise.decorators import disable_for_loaddata, enterprise_login_required
from enterprise.django_compatibility import reverse
from test_utils import get_magic_name, mock_view_function
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory


@mark.django_db
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
        self.provider_id = faker.slug()
        self.uuid = faker.uuid4()
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=self.customer)

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
        {'enterprise_uuid': FakerFactory.create().uuid4()},  # Invalid value of `enterprise_uuid` in kwargs.
    )
    def test_enterprise_login_required_raises_404(self, kwargs):
        """
        Test that the decorator `enterprise_login_required` raises `Http404`
        error when called with invalid or missing arguments.
        """
        view_function = mock_view_function()
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, 'course-v1:edX+DemoX+Demo_Course'],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        with raises(Http404):
            enterprise_login_required(view_function)(request, **kwargs)

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required_redirects_for_anonymous_users(self, mock_registry):
        """
        Test that the decorator `enterprise_login_required` returns Http
        Redirect for anonymous users.
        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=False)
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = AnonymousUser()

        response = enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when an anonymous
        # user tries to access enterprise course enrollment page.
        assert response.status_code == 302

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required(self, mock_registry):
        """
        Test that the enterprise login decorator calls the view function.

        Test that the decorator `enterprise_login_required` calls the view
        function when:
            1. `enterprise_uuid` is provided and corresponding enterprise
                customer exists in database.
            2. User making the request is authenticated.

        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=False)
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @mock.patch('enterprise.decorators.get_identity_provider', side_effect=ValueError)
    def test_enterprise_login_required_no_sso_provider(self, mock_registry):  # pylint: disable=unused-argument
        """
        Test that the enterprise login decorator calls the view function when no sso provider is configured.
        """

        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that view function was called.
        assert view_function.called

    @mock.patch('enterprise.utils.Registry')
    def test_enterprise_login_required_with_drop_existing_session(self, mock_registry):
        """
        Test that the enterprise login decorator redirects authenticated users with the appropriate provider config.
        """
        mock_registry.get.return_value.configure_mock(provider_id=self.provider_id, drop_existing_session=True)
        view_function = mock_view_function()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_dashboard_url = reverse(
            'enterprise_course_enrollment_page',
            args=[self.customer.uuid, course_id],
        )
        request = RequestFactory().get(enterprise_dashboard_url)
        request.user = UserFactory(is_active=True)

        response = enterprise_login_required(view_function)(
            request, enterprise_uuid=self.customer.uuid, course_id=course_id
        )

        # Assert that redirect status code 302 is returned when a logged in user comes in
        # with an sso provider set to drop existing sessions
        assert response.status_code == 302
