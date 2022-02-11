"""
Tests for the `integrated_channels` canvas configuration api.
"""
import json
from unittest import mock

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from test_utils import FAKE_UUIDS, APITest, factories


class CanvasConfigurationViewSetTests(APITest):
    """
    Tests for CanvasConfigurationViewSet REST endpoints
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

        self.enterprise_customer_conf = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            client_id='ayy',
            client_secret='lmao',
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_list(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].get('canvas_account_id'),
                         self.enterprise_customer_conf.canvas_account_id)
        self.assertEqual(data[0].get('enterprise_customer'),
                         self.enterprise_customer_conf.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-detail', args=[self.enterprise_customer_conf.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('canvas_account_id'),
                         self.enterprise_customer_conf.canvas_account_id)
        self.assertEqual(data.get('enterprise_customer'),
                         self.enterprise_customer_conf.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_post(self, mock_current_request):
        self.enterprise_customer_conf.delete()

        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-list')
        # using max value for BigintegerField
        payload = {
            'active': True,
            'canvas_account_id': 9223372036854775807,
            'enterprise_customer': self.enterprise_customer.uuid,
        }
        response = self.client.post(url, payload, format='json')
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data.get('canvas_account_id'), 9223372036854775807)
        self.assertEqual(data.get('enterprise_customer'), self.enterprise_customer.uuid)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-detail', args=[self.enterprise_customer_conf.id])
        payload = {
            'canvas_account_id': 1000,
            'enterprise_customer': FAKE_UUIDS[0],
        }
        response = self.client.put(url, payload)
        self.enterprise_customer_conf.refresh_from_db()
        self.assertEqual(self.enterprise_customer_conf.canvas_account_id, 1000)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_partial_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-detail', args=[self.enterprise_customer_conf.id])
        payload = {
            'canvas_account_id': 100,
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_destroy(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-detail', args=[self.enterprise_customer_conf.id])
        response = self.client.delete(url)
        configs = CanvasEnterpriseCustomerConfiguration.objects.filter()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(configs), 0)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_is_valid_field(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:canvas:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        # Assert that `is_valid` says a refresh token is missing
        assert data[0].get('is_valid').get('missing') == ['refresh_token']

        # Add a refresh token and assert that is_valid now passes
        self.enterprise_customer_conf.refresh_token = 'ayylmao'
        self.enterprise_customer_conf.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        assert not data[0].get('is_valid').get('missing')
