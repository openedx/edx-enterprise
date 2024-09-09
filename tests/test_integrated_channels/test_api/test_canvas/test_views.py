"""
Tests for the `integrated_channels` canvas configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.utils import localized_utcnow
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class CanvasConfigurationViewSetTests(APITest):
    """
    Tests for CanvasConfigurationViewSet REST endpoints
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

        self.enterprise_customer_conf = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            encrypted_client_id='ayy',
            encrypted_client_secret='lmao',
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_soft_deleted_content_in_lists(self, mock_current_request):
        factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            refresh_token='',
            deleted_at=localized_utcnow()
        )
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )

        url = reverse('api:v1:canvas:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        assert len(data) == 1
        assert data[0]['uuid'] == str(self.enterprise_customer_conf.uuid)
        assert len(CanvasEnterpriseCustomerConfiguration.all_objects.all()) == 2
        assert len(CanvasEnterpriseCustomerConfiguration.objects.all()) == 1

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
            'enterprise_customer': ENTERPRISE_ID,
            'encrypted_client_id': '',
            'encrypted_client_secret': '',
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

        self.enterprise_customer_conf.canvas_base_url = 'icky'
        self.enterprise_customer_conf.display_name = 'ickyickyickyickyickyickyickyicky'
        self.enterprise_customer_conf.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert missing.get('missing') == ['refresh_token']
        assert incorrect.get('incorrect') == ['canvas_base_url', 'display_name']

        self.enterprise_customer_conf.decrypted_client_id = ''
        self.enterprise_customer_conf.decrypted_client_secret = ''
        self.enterprise_customer_conf.canvas_base_url = ''
        self.enterprise_customer_conf.canvas_account_id = None
        self.enterprise_customer_conf.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['client_id', 'client_secret', 'canvas_base_url',
                                          'canvas_account_id', 'refresh_token']

        # Add a refresh token and assert that is_valid now passes
        self.enterprise_customer_conf.refresh_token = 'ayylmao'
        self.enterprise_customer_conf.canvas_base_url = 'http://lovely.com'
        self.enterprise_customer_conf.decrypted_client_id = '1'
        self.enterprise_customer_conf.decrypted_client_secret = '1'
        self.enterprise_customer_conf.canvas_account_id = 1
        self.enterprise_customer_conf.display_name = 'nice<3'
        self.enterprise_customer_conf.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
