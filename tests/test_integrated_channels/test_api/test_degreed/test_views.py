"""
Tests for the `integrated_channels` Degreed configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class DegreedConfigurationViewSetTests(APITest):
    """
    Tests for DegreedConfigurationViewSet REST endpoints
    """
    def setUp(self):
        super().setUp()
        self.set_jwt_cookie(self.client, [(ENTERPRISE_ADMIN_ROLE, ENTERPRISE_ID)])
        self.client.force_authenticate(user=self.user)

        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ENTERPRISE_ID)
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

        self.degreed_config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed:configuration-detail', args=[self.degreed_config.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data.get('degreed_company_id'), self.degreed_config.degreed_company_id)
        self.assertEqual(data.get('degreed_base_url'), self.degreed_config.degreed_base_url)
        self.assertEqual(data.get('degreed_user_id'), self.degreed_config.degreed_user_id)
        self.assertEqual(data.get('degreed_user_password'),
                         self.degreed_config.degreed_user_password)
        self.assertEqual(data.get('enterprise_customer'),
                         str(self.degreed_config.enterprise_customer.uuid))

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed:configuration-detail', args=[self.degreed_config.id])
        payload = {
            'degreed_base_url': 'http://testing2',
            'degreed_company_id': 'test',
            'enterprise_customer': ENTERPRISE_ID,
            'degreed_user_id': 893489,
            'degreed_user_password': 'password',
            'key': 'testing',
            'secret': 'secret',
        }
        response = self.client.put(url, payload)
        self.degreed_config.refresh_from_db()
        self.assertEqual(self.degreed_config.degreed_base_url, 'http://testing2')
        self.assertEqual(self.degreed_config.degreed_company_id, 'test')
        self.assertEqual(self.degreed_config.key, 'testing')
        self.assertEqual(self.degreed_config.secret, 'secret')
        self.assertEqual(self.degreed_config.degreed_user_password, 'password')
        self.assertEqual(self.degreed_config.degreed_user_id, '893489')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed:configuration-detail', args=[self.degreed_config.id])
        payload = {
            'degreed_base_url': 'http://testingchange',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.patch(url, payload)
        self.degreed_config.refresh_from_db()
        self.assertEqual(self.degreed_config.degreed_base_url, 'http://testingchange')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_delete(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:degreed:configuration-detail', args=[self.degreed_config.id])
        response = self.client.delete(url)
        configs = DegreedEnterpriseCustomerConfiguration.objects.filter()
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
        url = reverse('api:v1:degreed:configuration-list')

        self.degreed_config.degreed_base_url = ''
        self.degreed_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['key', 'secret', 'degreed_base_url']

        self.degreed_config.degreed_company_id = ''
        self.degreed_config.degreed_user_id = ''
        self.degreed_config.degreed_user_password = ''
        self.degreed_config.provider_id = ''
        self.degreed_config.degreed_base_url = 'badlink'
        self.degreed_config.display_name = 'helloihopeyourehavingagoodday'
        self.degreed_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert missing.get('missing') == ['key', 'secret', 'degreed_company_id', 'degreed_user_id',
                                          'degreed_user_password', 'provider_id']
        assert incorrect.get('incorrect') == ['degreed_base_url', 'display_name']

        self.degreed_config.key = 'ayy'
        self.degreed_config.secret = 'lmao'
        self.degreed_config.degreed_base_url = 'http://goodlink.com'
        self.degreed_config.provider_id = '1'
        self.degreed_config.degreed_company_id = '1'
        self.degreed_config.degreed_user_id = '1'
        self.degreed_config.degreed_user_password = '1'
        self.degreed_config.display_name = 'hithere'
        self.degreed_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
