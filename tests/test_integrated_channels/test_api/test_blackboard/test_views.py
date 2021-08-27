"""
Tests for the `integrated_channels` blackboard configuration api.
"""
import json

import mock

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
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
            'blackboard_base_url': 'http://testing2',
            'enterprise_customer': FAKE_UUIDS[0],
        }
        response = self.client.put(url, payload)
        self.enterprise_customer_conf.refresh_from_db()
        self.assertEqual(self.enterprise_customer_conf.client_secret, '1000')
        self.assertEqual(self.enterprise_customer_conf.client_id, '1001')
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
