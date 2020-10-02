# -*- coding: utf-8 -*-
"""
Tests for views in Blackboard integrated channel.
"""
from uuid import uuid4

import pytest
import responses
from rest_framework.test import APITestCase
from six.moves.urllib.parse import urljoin

from django.apps import apps
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils.http import urlencode

from enterprise.models import EnterpriseCustomer
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration

# TODO: Refactor candidate (duplication with canvas test_views)

ENTERPRISE_ID = str(uuid4())
BAD_ENTERPRISE_ID = str(uuid4())
SINGLE_CONFIG = {
    'client_id': 'id',
    'client_secret': 'secret',
    'base_url': 'http://betatest.blackboard.com',
}


@pytest.mark.django_db
class TestBlackboardAPIViews(APITestCase):
    """
    API Tests for BlackboardEnterpriseCustomerConfiguration REST endpoints.
    """

    def setUp(self):
        super(TestBlackboardAPIViews, self).setUp()
        self.site, _ = Site.objects.get_or_create(domain='http://example.com')
        self.enterprise_customer = EnterpriseCustomer.objects.create(
            uuid=ENTERPRISE_ID,
            name='test-ep',
            slug='test-ep',
            site=self.site,
            active=True,
        )
        self.app_config = apps.get_app_config('blackboard')
        self.refresh_token = 'test-refresh-token'
        self.urlbase = reverse('blackboard-oauth-complete')

        BlackboardEnterpriseCustomerConfiguration.objects.get_or_create(
            client_id=SINGLE_CONFIG['client_id'],
            client_secret=SINGLE_CONFIG['client_secret'],
            blackboard_base_url=SINGLE_CONFIG['base_url'],
            enterprise_customer=self.enterprise_customer,
            active=True,
            enterprise_customer_id=ENTERPRISE_ID,
        )

    def test_successful_refresh_token_request(self):
        """
        GET blackboard/oauth-complete?state=state?code=code
        w/ 200 Response
        """
        query_kwargs = {
            'state': ENTERPRISE_ID,
            'code': 'test-code'
        }
        oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))

        auth_token_url = urljoin(
            SINGLE_CONFIG['base_url'],
            self.app_config.oauth_token_auth_path
        )

        assert BlackboardEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer=self.enterprise_customer
        ).refresh_token == ''
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                auth_token_url,
                json={'refresh_token': self.refresh_token},
                status=200
            )
            self.client.get(oauth_complete_url)

        assert BlackboardEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer=self.enterprise_customer
        ).refresh_token == self.refresh_token

    def test_refresh_token_request_without_required_params(self):
        """
        GET blackboard/oauth-complete
        w/ 400 Response
        """
        query_kwargs_1 = {
            'code': 'test-code'
        }
        oauth_complete_url_without_id = '{}?{}'.format(
            self.urlbase, urlencode(query_kwargs_1)
        )
        response = self.client.get(oauth_complete_url_without_id)
        assert response.status_code == 400
        expected_string = "Enterprise ID (as 'state' url param) needed to obtain refresh token"
        assert response.json()['detail'] == expected_string

        query_kwargs_2 = {
            'state': ENTERPRISE_ID,
        }
        oauth_complete_url_without_code = '{}?{}'.format(
            self.urlbase, urlencode(query_kwargs_2)
        )
        response = self.client.get(oauth_complete_url_without_code)
        assert response.status_code == 400
        expected_string = "'code' url param was not provided, needed to obtain refresh token"
        assert response.json()['detail'] == expected_string

    def test_refresh_token_request_with_bad_enterprise_id(self):
        """
        GET blackboard/oauth-complete?state=<BAD STATE>?code=code
        """
        query_kwargs = {
            'state': BAD_ENTERPRISE_ID,
            'code': 'test-code'
        }
        oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))
        response = self.client.get(oauth_complete_url)

        assert response.status_code == 404
        assert response.json()['detail'] == 'No enterprise data found for given uuid: {}.'.format(
            BAD_ENTERPRISE_ID
        )

    def test_refresh_token_request_without_blackboard_config(self):
        """
        GET blackboard/oauth-complete?state=state?code=code
        """
        BlackboardEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer=self.enterprise_customer
        ).delete()
        query_kwargs = {
            'state': ENTERPRISE_ID,
            'code': 'test-code'
        }
        oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))
        response = self.client.get(oauth_complete_url)

        assert response.status_code == 404
        assert response.json()['detail'] == \
               'No Blackboard configuration found for enterprise: {}'.format(ENTERPRISE_ID)
