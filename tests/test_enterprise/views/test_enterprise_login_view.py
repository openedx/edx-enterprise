# -*- coding: utf-8 -*-
"""
Tests for the ``EnterpriseLoginView`` view of the Enterprise app.
"""

import ddt
import mock
from pytest import mark
from testfixtures import LogCapture

from django.test import Client
from django.urls import reverse

from enterprise.forms import ENTERPRISE_LOGIN_SUBTITLE, ENTERPRISE_LOGIN_TITLE, ERROR_MESSAGE_FOR_SLUG_LOGIN
from test_utils import EnterpriseFormViewTestCase
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory

IDENTITY_PROVIDER_PATH = 'enterprise.utils.get_identity_provider'
GET_PROVIDER_LOGIN_URL_PATH = 'enterprise.views.get_provider_login_url'

LOGGER_NAME = 'enterprise.forms'


@mark.django_db
@ddt.ddt
class TestEnterpriseLoginView(EnterpriseFormViewTestCase):
    """
    Test EnterpriseLoginView class.
    """
    url = reverse('enterprise_slug_login')
    template_path = 'enterprise.views.EnterpriseLoginView.template_name'

    def setUp(self):
        super().setUp()
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

    def _assert_post_request(
            self,
            enterprise_slug,
            registry_identity_provider,
            expected_status_code,
            expected_response
    ):
        """
        Assert the POST request.
        """
        post_data = {
            'enterprise_slug': enterprise_slug
        }

        with mock.patch(IDENTITY_PROVIDER_PATH) as mock_identity_provider:
            mock_identity_provider.return_value = registry_identity_provider
            if expected_status_code == 200:
                with mock.patch(GET_PROVIDER_LOGIN_URL_PATH) as mock_get_provider_login_url:
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
            'no_of_enterprise_customer_idp': 1,
            'has_default_idp': None,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': False,
            'enterprise_slug': 'incorrect_slug',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
            'expected_logger_message': '[Enterprise Slug Login] Not found enterprise: {}'
        },
        # Raise error if enable_slug_login is not enable.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': False,
            'no_of_enterprise_customer_idp': 1,
            'has_default_idp': None,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': False,
            'enterprise_slug': 'ec_slug',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
            'expected_logger_message': '[Enterprise Slug Login] slug login not enabled for enterprise: {}'
        },
        # Raise error if enterprise_customer is not linked to an idp.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': False,
            'no_of_enterprise_customer_idp': 1,
            'has_default_idp': None,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
            'expected_logger_message': '[Enterprise Slug Login] No IDP linked for enterprise: {}'
        },
        # Raise error if enterprise_customer is linked to an idp which not in the Registry Class.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'no_of_enterprise_customer_idp': 1,
            'has_default_idp': None,
            'registry_identity_provider': None,
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
            'expected_logger_message': '[Enterprise Slug Login] enterprise_customer linked to idp is not in the'
                                       ' Registry class for enterprise: {}'
        },
        # Raise error if enterprise_customer is linked to multiple IDPs and has no default IDP.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'no_of_enterprise_customer_idp': 2,
            'has_default_idp': False,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': [ERROR_MESSAGE_FOR_SLUG_LOGIN],
            'status_code': 400,
            'expected_logger_message': '[Enterprise Slug Login] No default IDP found for enterprise: {}'
        },
        # Valid request if enterprise_customer is linked to multiple IDPs and has default IDP.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'no_of_enterprise_customer_idp': 2,
            'has_default_idp': True,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': u'http://provider.login-url.com',
            'status_code': 200,
            'expected_logger_message': None
        },
        # Valid request.
        {
            'create_enterprise_customer': True,
            'create_enterprise_customer_idp': True,
            'no_of_enterprise_customer_idp': 1,
            'has_default_idp': None,
            'registry_identity_provider': 'some-dummy-provider',
            'enable_slug_login': True,
            'enterprise_slug': 'ec_slug_other',
            'expected_response': u'http://provider.login-url.com',
            'status_code': 200,
            'expected_logger_message': None
        },
    )
    def test_view_post(
            self,
            create_enterprise_customer,
            create_enterprise_customer_idp,
            no_of_enterprise_customer_idp,
            has_default_idp,
            registry_identity_provider,
            enable_slug_login,
            enterprise_slug,
            expected_response,
            status_code,
            expected_logger_message,
    ):
        """
        Test that view HTTP POST works as expected.
        """
        enterprise_customer = None
        if create_enterprise_customer:
            enterprise_customer = EnterpriseCustomerFactory(slug=enterprise_slug, enable_slug_login=enable_slug_login)

        if enterprise_customer and create_enterprise_customer_idp:
            ipds = EnterpriseCustomerIdentityProviderFactory.create_batch(
                no_of_enterprise_customer_idp, enterprise_customer=enterprise_customer
            )
            if has_default_idp:
                # pick last idp and make it default
                default_idp = ipds[-1]
                default_idp.default_provider = True
                default_idp.save()

        with LogCapture(LOGGER_NAME) as log:
            self._assert_post_request(enterprise_slug, registry_identity_provider, status_code, expected_response)
            if expected_logger_message:
                log.check_present(
                    (
                        LOGGER_NAME,
                        'ERROR',
                        expected_logger_message.format(enterprise_slug),
                    )
                )
