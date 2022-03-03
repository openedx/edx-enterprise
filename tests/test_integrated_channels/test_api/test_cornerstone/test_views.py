"""
Tests for the `integrated_channels` Cornerstone configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class CornerstoneConfigurationViewSetTests(APITest):
    """
    Tests for CornerstoneConfigurationViewSet REST endpoints
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

        self.cornerstone_config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:cornerstone:configuration-detail', args=[self.cornerstone_config.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('cornerstone_base_url'), self.cornerstone_config.cornerstone_base_url)
        self.assertEqual(data.get('enterprise_customer'),
                         str(self.cornerstone_config.enterprise_customer.uuid))

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:cornerstone:configuration-detail', args=[self.cornerstone_config.id])
        payload = {
            'cornerstone_base_url': 'http://testing2',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.put(url, payload)
        self.cornerstone_config.refresh_from_db()
        self.assertEqual(self.cornerstone_config.cornerstone_base_url, 'http://testing2')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:cornerstone:configuration-detail', args=[self.cornerstone_config.id])
        payload = {
            'cornerstone_base_url': 'http://testingchange',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.patch(url, payload)
        self.cornerstone_config.refresh_from_db()
        self.assertEqual(self.cornerstone_config.cornerstone_base_url, 'http://testingchange')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_delete(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:cornerstone:configuration-detail', args=[self.cornerstone_config.id])
        response = self.client.delete(url)
        configs = CornerstoneEnterpriseCustomerConfiguration.objects.filter()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(configs), 0)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_is_valid_field(self, mock_current_request):
        self.user.is_superuser = True
        self.user.save()

        # Give the config a reason to not be valid
        self.cornerstone_config.cornerstone_base_url = ''
        self.cornerstone_config.save()

        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:cornerstone:configuration-list')
        self.cornerstone_config.cornerstone_base_url = ''
        self.cornerstone_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['cornerstone_base_url']

        self.cornerstone_config.cornerstone_base_url = 'boo'
        self.cornerstone_config.display_name = 'oooogabooogaooogabooga'
        self.cornerstone_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        _, incorrect = data[0].get('is_valid')
        assert incorrect.get('incorrect') == ['cornerstone_base_url', 'display_name']

        # Add a url and assert that is_valid now passes
        self.cornerstone_config.cornerstone_base_url = 'http://ayylmao.com'
        self.cornerstone_config.display_name = 'hello'
        self.cornerstone_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
