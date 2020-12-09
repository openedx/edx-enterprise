import json
from uuid import uuid4

import mock

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class MoodleConfigurationViewSetTests(APITest):
    def setUp(self):
        super(MoodleConfigurationViewSetTests, self).setUp()
        self.set_jwt_cookie(self.client, [(ENTERPRISE_ADMIN_ROLE, ENTERPRISE_ID)])
        self.client.force_authenticate(user=self.user)

        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ENTERPRISE_ID)
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

        self.moodle_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id]) + '?enterprise_customer=' + ENTERPRISE_ID
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data.get('moodle_base_url'),
                         self.moodle_config.moodle_base_url)
        self.assertEqual(data.get('service_short_name'),
                         self.moodle_config.service_short_name)
        self.assertEqual(data.get('enterprise_customer'),
                         str(self.moodle_config.enterprise_customer.uuid))

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        payload = {
            'moodle_base_url': 'http://testing2',
            'service_short_name': 'test',
            'enterprise_customer': ENTERPRISE_ID,
            'token': 'testing'
        }
        response = self.client.put(url, payload)
        self.moodle_config.refresh_from_db()
        self.assertEqual(self.moodle_config.moodle_base_url, 'http://testing2')
        self.assertEqual(self.moodle_config.service_short_name, 'test')
        self.assertEqual(self.moodle_config.token, 'testing')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        payload = {
            'service_short_name': 'test2',
            'enterprise_customer': ENTERPRISE_ID,
        }
        response = self.client.patch(url, payload)
        self.moodle_config.refresh_from_db()
        self.assertEqual(self.moodle_config.service_short_name, 'test2')
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_delete(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        response = self.client.delete(url)
        configs = MoodleEnterpriseCustomerConfiguration.objects.filter()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(configs), 0)
