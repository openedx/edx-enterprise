"""
Tests for the ``EnterpriseProxyLoginView`` view of the Enterprise app.
"""

import ddt

from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.views import LMS_LOGIN_URL
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory


@ddt.ddt
class TestEnterpriseProxyLoginView(TestCase):
    """
    Test EnterpriseProxyLoginView class.
    """
    base_url = reverse('enterprise_proxy_login')
    next_url = 'http://localhost:18000'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.client = Client()
        cls.enterprise_customer = EnterpriseCustomerFactory()
        cls.identity_provider = EnterpriseCustomerIdentityProviderFactory(enterprise_customer=cls.enterprise_customer)

    def _get_url_with_params(self, use_enterprise_slug=True, use_next=True, enterprise_slug_override=None,
                             next_override=None):
        """
        Helper to add the appropriate query parameters if specified and assert the correct response status.
        """
        query_params = QueryDict(mutable=True)
        if use_enterprise_slug:
            query_params['enterprise_slug'] = enterprise_slug_override or self.enterprise_customer.slug
        if use_next:
            query_params['next'] = next_override or self.next_url
        url = self.base_url + '/?' + query_params.urlencode()
        return url

    @ddt.data(
        {'use_enterprise_slug': False, 'enterprise_slug': None},
        {'use_enterprise_slug': True, 'enterprise_slug': 'missing-slug'},
    )
    @ddt.unpack
    def test_missing_slug(self, use_enterprise_slug, enterprise_slug):
        """
        Verify the view 404s if no slug or a slug not associated with an enterprise customer is used.
        """
        url = self._get_url_with_params(
            use_enterprise_slug=use_enterprise_slug,
            enterprise_slug_override=enterprise_slug,
        )
        response = self.client.get(url)
        assert response.status_code == 404

    def test_redirect_no_tpa(self):
        """
        Verify the view redirects without tpa_hint if the enterprise has no identity provider.
        """
        customer_without_tpa = EnterpriseCustomerFactory()
        url = self._get_url_with_params(enterprise_slug_override=customer_without_tpa.slug, use_next=False)
        response = self.client.get(url)
        self.assertRedirects(response, LMS_LOGIN_URL, fetch_redirect_response=False)

    def test_tpa_redirect(self):
        """
        Verify the view adds the next param and the tpa_hint to the redirect if the enterprise has an identity provider.
        """
        url = self._get_url_with_params()
        response = self.client.get(url)
        query_params = QueryDict(mutable=True)
        query_params['next'] = self.next_url
        query_params['tpa_hint'] = self.enterprise_customer.identity_provider
        expected_url = LMS_LOGIN_URL + '?' + query_params.urlencode()
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
