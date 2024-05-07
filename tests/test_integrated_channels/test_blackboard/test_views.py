"""
Tests for views in Blackboard integrated channel.
"""
import logging
from urllib.parse import urljoin
from uuid import uuid4

import pytest
import responses
from rest_framework.test import APITestCase
from testfixtures import LogCapture

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
    'uuid': '123e4567-e89b-12d3-a456-426655440001',
    'client_id': 'id',
    'client_secret': 'secret',
    'base_url': 'http://betatest.blackboard.com',
}
SECOND_CONFIG = {
    'uuid': '123e4567-e89b-12d3-a456-426655440002',
    'client_id': 'id2',
    'client_secret': 'secret2',
    'base_url': 'http://betatest2.blackboard.com',
}


@pytest.mark.django_db
class TestBlackboardAPIViews(APITestCase):
    """
    API Tests for BlackboardEnterpriseCustomerConfiguration REST endpoints.
    """

    def setUp(self):
        super().setUp()
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

        try: 
            BlackboardEnterpriseCustomerConfiguration.objects.get(
                uuid=SINGLE_CONFIG['uuid'],
                blackboard_base_url=SINGLE_CONFIG['base_url'],
                enterprise_customer=self.enterprise_customer,
                active=True,
                enterprise_customer_id=ENTERPRISE_ID,
            )
        except BlackboardEnterpriseCustomerConfiguration.DoesNotExist:
            BlackboardEnterpriseCustomerConfiguration.objects.create(
                uuid=SINGLE_CONFIG['uuid'],
                decrypted_client_id=SINGLE_CONFIG['client_id'],
                decrypted_client_secret=SINGLE_CONFIG['client_secret'],
                blackboard_base_url=SINGLE_CONFIG['base_url'],
                enterprise_customer=self.enterprise_customer,
                active=True,
                enterprise_customer_id=ENTERPRISE_ID,
            )
        try: 
            BlackboardEnterpriseCustomerConfiguration.objects.get(
                uuid=SECOND_CONFIG['uuid'],
                blackboard_base_url=SECOND_CONFIG['base_url'],
                enterprise_customer=self.enterprise_customer,
                active=True,
                enterprise_customer_id=ENTERPRISE_ID,
            )
        except BlackboardEnterpriseCustomerConfiguration.DoesNotExist:
            BlackboardEnterpriseCustomerConfiguration.objects.create(
                uuid=SECOND_CONFIG['uuid'],
                decrypted_client_id=SECOND_CONFIG['client_id'],
                decrypted_client_secret=SECOND_CONFIG['client_secret'],
                blackboard_base_url=SECOND_CONFIG['base_url'],
                enterprise_customer=self.enterprise_customer,
                active=True,
                enterprise_customer_id=ENTERPRISE_ID,
            )

    def test_successful_refresh_token_by_uuid_request(self):
        """
        GET blackboard/oauth-complete?state=config_uuid?code=code
        w/ 200 Response
        """
        query_kwargs = {
            'state': SINGLE_CONFIG['uuid'],
            'code': 'test-code'
        }
        oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))

        auth_token_url = urljoin(
            SINGLE_CONFIG['base_url'],
            self.app_config.oauth_token_auth_path
        )

        assert BlackboardEnterpriseCustomerConfiguration.objects.get(
            uuid=SINGLE_CONFIG['uuid']
        ).refresh_token == ''
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                auth_token_url,
                json={'refresh_token': self.refresh_token, 'token_type': 'refresh_token', 'expires_in': '2020-02-01'},
                status=200
            )
            response = self.client.get(oauth_complete_url)
            assert response.status_code == 200
            assert BlackboardEnterpriseCustomerConfiguration.objects.get(
                uuid=SINGLE_CONFIG['uuid']
            ).refresh_token == self.refresh_token

    def test_successful_refresh_token_by_legacy_customer_uuid_request(self):
        """
        GET blackboard/oauth-complete?state=enterprise_customer_uuid?code=code
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

        assert BlackboardEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=self.enterprise_customer
        ).first().refresh_token == ''
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                auth_token_url,
                json={'refresh_token': self.refresh_token, 'token_type': 'refresh_token', 'expires_in': '2020-02-01'},
                status=200
            )
            response = self.client.get(oauth_complete_url)
            assert response.status_code == 200
            assert BlackboardEnterpriseCustomerConfiguration.objects.filter(
                enterprise_customer=self.enterprise_customer
            ).first().refresh_token == self.refresh_token

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
        with LogCapture(level=logging.ERROR) as log_capture:
            self.client.get(oauth_complete_url_without_id)
            expected_string = "Blackboard Configuration uuid (as 'state' url param) needed to obtain refresh token"
            assert expected_string in log_capture.records[0].getMessage()

        query_kwargs_2 = {
            'state': ENTERPRISE_ID,
        }
        oauth_complete_url_without_code = '{}?{}'.format(
            self.urlbase, urlencode(query_kwargs_2)
        )
        with LogCapture(level=logging.ERROR) as log_capture:
            self.client.get(oauth_complete_url_without_code)
            expected_string = "'code' url param was not provided, needed to obtain refresh token"
            assert expected_string in log_capture.records[0].getMessage()

    def test_refresh_token_request_with_bad_enterprise_id(self):
        """
        GET blackboard/oauth-complete?state=<BAD STATE>?code=code
        """
        query_kwargs = {
            'state': BAD_ENTERPRISE_ID,
            'code': 'test-code'
        }
        oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))
        with LogCapture(level=logging.ERROR) as log_capture:
            self.client.get(oauth_complete_url)
            assert 'No state data found for given uuid' in log_capture.records[0].getMessage()

    def test_refresh_token_request_without_blackboard_config(self):
        """
        GET blackboard/oauth-complete?state=state?code=code
        """
        query_kwargs = {
            'state': 'BADCODE',
            'code': 'test-code'
        }
        with LogCapture(level=logging.ERROR) as log_capture:
            oauth_complete_url = '{}?{}'.format(self.urlbase, urlencode(query_kwargs))
            self.client.get(oauth_complete_url)
            assert 'No state data found for given uuid' in log_capture.records[0].getMessage()
