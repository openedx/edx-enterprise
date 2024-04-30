"""
Tests for the `integrated_channels` blackboard configuration api.
"""
import json
from unittest import mock

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.utils import localized_utcnow
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration
from test_utils import FAKE_UUIDS, APITest, factories


class BlackboardConfigurationViewSetTests(APITest):
    """
    Tests for BlackboardConfigurationViewSet REST endpoints
    """

    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

        self.enterprise_customer_conf = factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            refresh_token='',
        )

        self.global_config = factories.BlackboardGlobalConfigurationFactory(
            app_key='test_app_key',
            decrypted_app_secret='test_app_secret',
            enabled=True,
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_soft_deleted_content_in_lists(self, mock_current_request):
        factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            refresh_token='',
            deleted_at=localized_utcnow()
        )
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        assert len(data) == 1
        assert data[0]['uuid'] == str(self.enterprise_customer_conf.uuid)
        assert len(BlackboardEnterpriseCustomerConfiguration.all_objects.all()) == 2
        assert len(BlackboardEnterpriseCustomerConfiguration.objects.all()) == 1

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_list(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].get('client_id'),
                         str(self.enterprise_customer_conf.client_id))
        self.assertEqual(data[0].get('client_secret'),
                         str(self.enterprise_customer_conf.client_secret))
        self.assertEqual(data[0].get('refresh_token'), '')
        self.assertEqual(data[0].get('enterprise_customer'),
                         self.enterprise_customer_conf.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-detail', args=[self.enterprise_customer_conf.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('blackboard_base_url'),
                         self.enterprise_customer_conf.blackboard_base_url)
        self.assertEqual(data.get('client_id'),
                         str(self.enterprise_customer_conf.client_id))
        self.assertEqual(data.get('client_secret'),
                         str(self.enterprise_customer_conf.client_secret))
        self.assertEqual(data.get('enterprise_customer'),
                         self.enterprise_customer_conf.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_post(self, mock_current_request):
        self.enterprise_customer_conf.delete()
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-list')
        payload = {
            'active': True,
            'client_id': 1,
            'client_secret': 2,
            'enterprise_customer': self.enterprise_customer.uuid,
        }
        response = self.client.post(url, payload, format='json')
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data.get('client_id'), '1')
        self.assertEqual(data.get('client_secret'), '2')
        self.assertEqual(data.get('active'), True)
        self.assertEqual(data.get('enterprise_customer'), self.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-detail', args=[self.enterprise_customer_conf.id])
        payload = {
            'client_secret': 1000,
            'client_id': 1001,
            'encrypted_client_secret': 1000,
            'encrypted_client_id': 1001,
            'blackboard_base_url': 'http://testing2',
            'enterprise_customer': FAKE_UUIDS[0],
        }
        response = self.client.put(url, payload)
        self.enterprise_customer_conf.refresh_from_db()
        self.assertEqual(self.enterprise_customer_conf.client_secret, '1000')
        self.assertEqual(self.enterprise_customer_conf.client_id, '1001')
        self.assertEqual(self.enterprise_customer_conf.decrypted_client_secret, '1000')
        self.assertEqual(self.enterprise_customer_conf.decrypted_client_id, '1001')
        self.assertEqual(self.enterprise_customer_conf.blackboard_base_url, 'http://testing2')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_partial_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-detail', args=[self.enterprise_customer_conf.id])
        payload = {
            'client_id': 10001,
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_destroy(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-detail', args=[self.enterprise_customer_conf.id])
        response = self.client.delete(url)
        configs = BlackboardEnterpriseCustomerConfiguration.objects.filter()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(configs), 0)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_is_valid_field(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:configuration-list')
        self.enterprise_customer_conf.blackboard_base_url = ''
        self.enterprise_customer_conf.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['blackboard_base_url', 'refresh_token']

        self.enterprise_customer_conf.blackboard_base_url = 'bleh'
        self.enterprise_customer_conf.display_name = 'loooooooooooooooooooongname'
        self.enterprise_customer_conf.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert missing.get('missing') == ['refresh_token']
        assert incorrect.get('incorrect') == ['blackboard_base_url', 'display_name']

        self.enterprise_customer_conf.refresh_token = 'ayylmao'
        self.enterprise_customer_conf.client_id = '1'
        self.enterprise_customer_conf.client_secret = '1'
        self.enterprise_customer_conf.blackboard_base_url = 'http://better.com'
        self.enterprise_customer_conf.display_name = 'shortname'
        self.enterprise_customer_conf.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_global_config_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:blackboard:global-configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('count'), 1)
        self.assertEqual(data.get('results')[0].get('app_key'), str(self.global_config.app_key))
        assert not data.get('results')[0].get('app_secret')

        self.assertTrue(hasattr(self.global_config, 'decrypted_app_secret'))
        self.assertIsNotNone(self.global_config.encrypted_app_secret)
        self.global_config.encrypted_app_secret = ''
        self.global_config.save()
        self.assertTrue(hasattr(self.global_config, 'decrypted_app_secret'))
        self.assertEqual(self.global_config.encrypted_app_secret, '')
