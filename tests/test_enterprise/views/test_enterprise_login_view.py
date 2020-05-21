# -*- coding: utf-8 -*-
"""
Tests for the ``EnterpriseLoginView`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from pytest import mark

from django.test import Client
from django.urls import reverse

from enterprise.forms import ENTERPRISE_LOGIN_SUBTITLE, ENTERPRISE_LOGIN_TITLE, ERROR_MESSAGE_FOR_SLUG_LOGIN
from test_utils import EnterpriseFormViewTestCase
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory

IDENTITY_PROVIDER_PATH = 'enterprise.models.EnterpriseCustomerIdentityProvider.identity_provider'
GET_PROVIDER_LOGIN_URL_PATH = 'enterprise.views.get_provider_login_url'


@mark.django_db
@ddt.ddt
class TestEnterpriseLoginView(EnterpriseFormViewTestCase):
    """
    Test EnterpriseLoginView class.
    """
    url = reverse('enterprise_slug_login')
    template_path = 'enterprise.views.EnterpriseLoginView.template_name'

    def setUp(self):
        super(TestEnterpriseLoginView, self).setUp()
        self.client = Client()

    def test_view_get(self):
        """
        Test that view HTTP GET works as expected.
        """
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.context['enterprise_login_title_message'] == ENTERPRISE_LOGIN_TITLE
        assert response.context['enterprise_login_subtitle_message'] == ENTERPRISE_LOGIN_SUBTITLE
        assert list(response.context['form'].fields.keys())[0] == 'enterprise_slug'

    def _assert_post_request(self, enterprise_slug, expected_status_code, expected_response):
        """
        Assert the POST request.
        """
        post_data = {
            'enterprise_slug': enterprise_slug
        }
        if expected_status_code == 200:
            with mock.patch(IDENTITY_PROVIDER_PATH) as mock_identity_provider:
                with mock.patch(GET_PROVIDER_LOGIN_URL_PATH) as mock_get_provider_login_url:
                    mock_identity_provider.return_value = 'some-dummy-provider'
                    mock_get_provider_login_url.return_value = expected_response
                    response = self.client.post(self.url, post_data)
                    assert response.status_code == expected_status_code
                    assert response.json().get('url') == expected_response
        else:
            response = self.client.post(self.url, post_data)
            assert response.status_code == expected_status_code
            assert response.json().get('errors') == expected_response

    @ddt.unpack
    @ddt.data(
        # Raise error if slug is wrong.
        {
            'create_enterprise_customer': False,
            'create_enterprise_customer_idp': False,
            'enable_slug_login': False,
            'enterprise_slug': 'incorrect_slug',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
        },
        # Raise error if enable_slug_login is not enable.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': False,
            'enable_slug_login': False,
            'enterprise_slug': 'ec_slug',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
        },
        # Raise error if enterprise_customer is not linked to an idp.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': False,
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
        },
        # Raise error if enterprise_customer is linked to an idp which not in the Registry Class.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
        },
        # Valid request.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': u'http://provider.login-url.com',
            'status_code': 200,
        },
    )
    def test_view_post(
            self,
            create_enterprise_customer,
            create_enterprise_customer_idp,
            enable_slug_login,
            enterprise_slug,
            expected_response,
            status_code
    ):
        """
        Test that view HTTP POST works as expected.
        """
        enterprise_customer = None
        if create_enterprise_customer:
            enterprise_customer = EnterpriseCustomerFactory(slug=enterprise_slug, enable_slug_login=enable_slug_login)

        if enterprise_customer and create_enterprise_customer_idp:
            EnterpriseCustomerIdentityProviderFactory(enterprise_customer=enterprise_customer)

        self._assert_post_request(enterprise_slug, status_code, expected_response)
