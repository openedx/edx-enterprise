"""
Tests for the `integrated_channels` Degreed2 configuration api.
"""
import json
from uuid import uuid4

import mock

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.utils import localized_utcnow
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class Degreed2ConfigurationViewSetTests(APITest):
    """
    Tests for Degreed2ConfigurationViewSet REST endpoints
    """
    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ENTERPRISE_ID)
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

        self.degreed2_config = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_soft_deleted_content_in_lists(self, mock_current_request):
        factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            deleted_at=localized_utcnow(),
        )
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )

        url = reverse('api:v1:degreed2:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        assert len(data) == 1
        assert data[0]['id'] == self.degreed2_config.id
        assert len(Degreed2EnterpriseCustomerConfiguration.all_objects.all()) == 2
        assert len(Degreed2EnterpriseCustomerConfiguration.objects.all()) == 1

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed2:configuration-detail', args=[self.degreed2_config.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data.get('degreed_base_url'), self.degreed2_config.degreed_base_url)
        self.assertEqual(data.get('encrypted_client_id'), self.degreed2_config.encrypted_client_id)
        self.assertEqual(data.get('encrypted_client_secret'), self.degreed2_config.encrypted_client_secret)
        self.assertEqual(data.get('degreed_token_fetch_base_url'), self.degreed2_config.degreed_token_fetch_base_url)
        self.assertEqual(data.get('enterprise_customer'),
                         str(self.degreed2_config.enterprise_customer.uuid))

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed2:configuration-detail', args=[self.degreed2_config.id])
        payload = {
            'degreed_base_url': 'http://testing2',
            'degreed_token_fetch_base_url': 'foobar',
            'enterprise_customer': ENTERPRISE_ID,
            'encrypted_client_id': 'testing',
            'encrypted_client_secret': 'secret',
        }
        response = self.client.put(url, payload)
        self.degreed2_config.refresh_from_db()
        self.assertEqual(self.degreed2_config.degreed_base_url, 'http://testing2')
        self.assertEqual(self.degreed2_config.encrypted_client_id, 'testing')
        self.assertEqual(self.degreed2_config.encrypted_client_secret, 'secret')
        self.assertEqual(self.degreed2_config.degreed_token_fetch_base_url, 'foobar')
        self.assertEqual(str(self.degreed2_config.enterprise_customer.uuid), ENTERPRISE_ID)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed2:configuration-detail', args=[self.degreed2_config.id])
        payload = {
            'degreed_base_url': 'http://testingchange',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.patch(url, payload)
        self.degreed2_config.refresh_from_db()
        self.assertEqual(self.degreed2_config.degreed_base_url, 'http://testingchange')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_delete(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed2:configuration-detail', args=[self.degreed2_config.id])
        self.assertEqual(len(Degreed2EnterpriseCustomerConfiguration.objects.filter()), 1)
        response = self.client.delete(url)
        configs = Degreed2EnterpriseCustomerConfiguration.objects.filter()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(configs), 0)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_is_valid_field(self, mock_current_request):
        self.user.is_superuser = True
        self.user.save()

        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed2:configuration-list')

        self.degreed2_config.client_id = ''
        self.degreed2_config.client_secret = ''
        self.degreed2_config.degreed_base_url = ''
        self.degreed2_config.degreed_token_fetch_base_url = ''
        self.degreed2_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['client_id', 'client_secret', 'degreed_base_url']

        self.degreed2_config.degreed_base_url = 'eww'
        self.degreed2_config.display_name = 'thisisagrosslongdisplayname'
        self.degreed2_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        _, incorrect = data[0].get('is_valid')
        assert incorrect.get('incorrect') == ['degreed_base_url', 'display_name']

        # Add a client id and proper url and assert that is_valid now passes
        self.degreed2_config.client_id = 'ayylmao'
        self.degreed2_config.client_secret = 'whatsup'
        self.degreed2_config.degreed_base_url = 'http://nice.com'
        self.degreed2_config.display_name = 'lovely'
        self.degreed2_config.degreed_token_fetch_base_url = 'http://hey.com'
        self.degreed2_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
