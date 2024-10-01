"""
Tests for the ``EnterpriseProxyLoginView`` view of the Enterprise app.
"""

import uuid

import ddt

from django.conf import settings
from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.views import LMS_REGISTER_URL
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerInviteKeyFactory,
)


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
        cls.enterprise_customer_invite_key = EnterpriseCustomerInviteKeyFactory(
            enterprise_customer=cls.enterprise_customer,
        )
        cls.identity_provider = EnterpriseCustomerIdentityProviderFactory(enterprise_customer=cls.enterprise_customer)

    def _get_url_with_params(self, use_enterprise_slug=True, use_next=True, enterprise_slug_override=None,
                             next_override=None, use_invite_key=False, invite_key_override=None, tpa_hint=None):
        """
        Helper to add the appropriate query parameters if specified and assert the correct response status.
        """
        query_params = QueryDict(mutable=True)
        if use_enterprise_slug:
            query_params['enterprise_slug'] = enterprise_slug_override or self.enterprise_customer.slug
        if use_invite_key:
            query_params['enterprise_customer_invite_key'] = (
                invite_key_override or str(self.enterprise_customer_invite_key.uuid)
            )
        if use_next:
            query_params['next'] = next_override or self.next_url
        if tpa_hint:
            query_params['tpa_hint'] = tpa_hint
        url = self.base_url + '/?' + query_params.urlencode()
        return url

    @ddt.data(
        {'use_enterprise_slug': False, 'enterprise_slug': None},
        {'use_enterprise_slug': True, 'enterprise_slug': 'missing-slug'},
    )
    @ddt.unpack
    def test_missing_slug(self, use_enterprise_slug, enterprise_slug):
        """
        Verify the view 404s if no slug or a slug not associated with an enterprise
        customer is used.
        """
        url = self._get_url_with_params(
            use_enterprise_slug=use_enterprise_slug,
            enterprise_slug_override=enterprise_slug,
        )
        response = self.client.get(url)
        assert response.status_code == 404

    @ddt.data(
        {'use_invite_key': True, 'invite_key_uuid': uuid.uuid4()},
        {'use_invite_key': False, 'invite_key_uuid': None},
    )
    @ddt.unpack
    def test_missing_invite_key(self, use_invite_key, invite_key_uuid):
        """
        Verify the view 404s if no invite key or a invite key not associated with an enterprise
        customer is used.
        """
        url = self._get_url_with_params(
            use_enterprise_slug=False,
            use_invite_key=use_invite_key,
            invite_key_override=str(invite_key_uuid),
        )
        response = self.client.get(url)
        assert response.status_code == 404

    @ddt.data(
        {
            'use_next': True,  # 'next' query param is passed in URL
            'use_slug': True,
            'use_invite_key': False,
        },
        {
            'use_next': False,  # 'next' query param not passed, default to LP URL with slug
            'use_slug': True,
            'use_invite_key': False,
        },
        {
            'use_next': True,  # 'next' query param is passed in URL
            'use_slug': False,
            'use_invite_key': True,
        },
        {
            'use_next': False,  # 'next' query param not passed, default to LP URL with slug
            'use_slug': False,
            'use_invite_key': True,
        },
    )
    @ddt.unpack
    def test_slug_redirect_no_tpa(self, use_next, use_slug, use_invite_key):
        """
        Verify the view redirects without tpa_hint if the enterprise has no identity provider.
        """
        customer_without_tpa = EnterpriseCustomerFactory()
        customer_invite_key = EnterpriseCustomerInviteKeyFactory(
            enterprise_customer=customer_without_tpa,
        )
        url = self._get_url_with_params(
            use_enterprise_slug=use_slug,
            enterprise_slug_override=customer_without_tpa.slug,
            use_invite_key=use_invite_key,
            invite_key_override=str(customer_invite_key.uuid),
            use_next=use_next,
        )
        response = self.client.get(url)
        query_params = QueryDict(mutable=True)
        query_params['enterprise_customer'] = str(customer_without_tpa.uuid)
        if use_next:
            query_params['next'] = self.next_url
        else:
            learner_portal_url = settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL
            query_params['next'] = learner_portal_url + '/' + customer_without_tpa.slug
        query_params['proxy_login'] = True
        expected_url = LMS_REGISTER_URL + '?' + query_params.urlencode()
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @ddt.data(
        {
            'use_next': True,  # 'next' query param is passed in URL
            'use_slug': True,
            'use_invite_key': False,
        },
        {
            'use_next': False,  # 'next' query param not passed, default to LP URL with slug
            'use_slug': True,
            'use_invite_key': False,
        },
        {
            'use_next': True,  # 'next' query param is passed in URL
            'use_slug': False,
            'use_invite_key': True,
        },
        {
            'use_next': False,  # 'next' query param not passed, default to LP URL with slug
            'use_slug': False,
            'use_invite_key': True,
        },
    )
    @ddt.unpack
    def test_slug_tpa_redirect(self, use_next, use_slug, use_invite_key):
        """
        Verify the view adds the next param and the tpa_hint to the redirect if the enterprise has an identity provider.
        """
        url = self._get_url_with_params(
            use_enterprise_slug=use_slug,
            use_invite_key=use_invite_key,
            use_next=use_next,
        )
        response = self.client.get(url)
        query_params = QueryDict(mutable=True)
        if use_next:
            next_url = self.next_url
        else:
            learner_portal_url = settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL
            next_url = learner_portal_url + '/' + self.enterprise_customer.slug
        query_params['next'] = f'{next_url}?tpa_hint={self.enterprise_customer.identity_provider}'
        expected_url = LMS_REGISTER_URL + '?' + query_params.urlencode()
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @ddt.data(
        ('idp-1', 'idp-1', True, 'idp-1'),
        (None, 'idp-1', True, 'idp-1'),
        ('fake_idp', 'idp-1', True, None),
        ('idp-1', 'idp-1', False, None),
        (None, None, False, None),
    )
    @ddt.unpack
    def test_tpa_redirects_using_tpa_hint_param(
            self,
            tpa_hint_param,
            identity_provider_id,
            link_identity_provider,
            redirected_tpa_hint
    ):
        """
        Verify the view adds the tpa_hint to the redirect if there is a tpa_hint provided in the query_param.
        """

        enterprise_customer = EnterpriseCustomerFactory()
        identity_provider = EnterpriseCustomerIdentityProviderFactory()

        if identity_provider_id:
            identity_provider.provider_id = identity_provider_id
            identity_provider.save()

        if link_identity_provider:
            identity_provider.enterprise_customer = enterprise_customer
            identity_provider.save()

        url = self._get_url_with_params(enterprise_slug_override=enterprise_customer.slug, tpa_hint=tpa_hint_param)
        response = self.client.get(url)
        query_params = QueryDict(mutable=True)
        next_url = self.next_url

        if redirected_tpa_hint:
            query_params['next'] = f'{next_url}?tpa_hint={redirected_tpa_hint}'
        else:
            query_params['enterprise_customer'] = str(enterprise_customer.uuid)
            query_params['proxy_login'] = True
            query_params['next'] = next_url
        expected_url = f'{LMS_REGISTER_URL}?{query_params.urlencode()}'
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
