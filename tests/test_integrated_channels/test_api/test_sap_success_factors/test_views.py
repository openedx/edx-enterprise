"""
Tests for the `integrated_channels` success factors configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class SAPSuccessFactorsConfigurationViewSetTests(APITest):
    """
    Tests for SAPSuccessFactorsConfigurationViewSet REST endpoints
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

        self.sap_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:sap_success_factors:configuration-detail', args=[self.sap_config.id])
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('sapsf_base_url'),
                         self.sap_config.sapsf_base_url)
        self.assertEqual(data.get('sapsf_company_id'),
                         self.sap_config.sapsf_company_id)
        self.assertEqual(int(data.get('sapsf_user_id')),
                         self.sap_config.sapsf_user_id)
        self.assertEqual(data.get('key'),
                         self.sap_config.key)
        self.assertEqual(data.get('secret'),
                         self.sap_config.secret)
        self.assertEqual(data.get('user_type'),
                         self.sap_config.user_type)
        self.assertEqual(data.get('enterprise_customer'),
                         str(self.sap_config.enterprise_customer.uuid))

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:sap_success_factors:configuration-detail', args=[self.sap_config.id])
        payload = {
            'sapsf_base_url': 'http://testing2',
            'sapsf_company_id': 'test',
            'enterprise_customer': ENTERPRISE_ID,
            'sapsf_user_id': 893489,
            'key': 'testing',
            'secret': 'secret',
            'user_type': 'user',
        }
        response = self.client.put(url, payload)
        self.sap_config.refresh_from_db()
        self.assertEqual(self.sap_config.sapsf_base_url, 'http://testing2')
        self.assertEqual(self.sap_config.sapsf_company_id, 'test')
        self.assertEqual(self.sap_config.key, 'testing')
        self.assertEqual(self.sap_config.secret, 'secret')
        self.assertEqual(self.sap_config.user_type, 'user')
        self.assertEqual(self.sap_config.sapsf_user_id, '893489')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:sap_success_factors:configuration-detail', args=[self.sap_config.id])
        payload = {
            'sapsf_base_url': 'http://testingchange',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.patch(url, payload)
        self.sap_config.refresh_from_db()
        self.assertEqual(self.sap_config.sapsf_base_url, 'http://testingchange')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_delete(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:sap_success_factors:configuration-detail', args=[self.sap_config.id])
        response = self.client.delete(url)
        configs = SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.filter()
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
        url = reverse('api:v1:sap_success_factors:configuration-list')

        self.sap_config.sapsf_base_url = 'sad'
        self.sap_config.display_name = 'suchalongdisplaynamelikewowww'
        self.sap_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        missing, incorrect = data[0].get('is_valid')
        assert missing.get('missing') == ['key', 'secret']
        assert incorrect.get('incorrect') == ['sapsf_base_url', 'display_name']

        self.sap_config.sapsf_base_url = ''
        self.sap_config.sapsf_company_id = ''
        self.sap_config.sapsf_user_id = ''
        self.sap_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['key', 'sapsf_base_url', 'sapsf_company_id', 'sapsf_user_id', 'secret']

        self.sap_config.key = 'ayy'
        self.sap_config.secret = 'lmao'
        self.sap_config.sapsf_company_id = '1'
        self.sap_config.sapsf_user_id = '1'
        self.sap_config.sapsf_base_url = 'http://happy.com'
        self.sap_config.display_name = 'better'
        self.sap_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
