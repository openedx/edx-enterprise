"""
Tests for the `integrated_channels` moodle configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.utils import localized_utcnow
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class MoodleConfigurationViewSetTests(APITest):
    """
    Tests for MoodleConfigurationViewSet REST endpoints
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

        self.moodle_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_create_with_token(self, mock_current_request):
        """Test creating a new MoodleEnterpriseCustomerConfiguration with token authentication."""
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-list')
        payload = {
            'moodle_base_url': 'http://test-moodle.com',
            'service_short_name': 'test_service',
            'enterprise_customer': ENTERPRISE_ID,
            'token': 'test_token',
            'display_name': 'Test Moodle Config'
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 201)

        # Verify the configuration was created correctly
        config = MoodleEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer__uuid=ENTERPRISE_ID,
            moodle_base_url='http://test-moodle.com'
        )
        self.assertEqual(config.service_short_name, 'test_service')
        self.assertEqual(config.decrypted_token, 'test_token')
        self.assertIsNone(config.decrypted_username)
        self.assertIsNone(config.decrypted_password)
        self.assertEqual(config.display_name, 'Test Moodle Config')

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_create_with_username_password(self, mock_current_request):
        """Test creating a new MoodleEnterpriseCustomerConfiguration with username/password authentication."""
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-list')
        payload = {
            'moodle_base_url': 'http://test-moodle2.com',
            'service_short_name': 'test_service2',
            'enterprise_customer': ENTERPRISE_ID,
            'username': 'test_user',
            'password': 'test_pass',
            'display_name': 'Test Moodle Config 2'
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 201)

        # Verify the configuration was created correctly
        config = MoodleEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer__uuid=ENTERPRISE_ID,
            moodle_base_url='http://test-moodle2.com'
        )
        self.assertEqual(config.service_short_name, 'test_service2')
        self.assertEqual(config.decrypted_username, 'test_user')
        self.assertEqual(config.decrypted_password, 'test_pass')
        self.assertIsNone(config.decrypted_token)
        self.assertEqual(config.display_name, 'Test Moodle Config 2')

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_soft_deleted_content_in_lists(self, mock_current_request):
        factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            deleted_at=localized_utcnow()
        )
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )

        url = reverse('api:v1:moodle:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        assert len(data) == 1
        assert data[0]['id'] == self.moodle_config.id
        assert len(MoodleEnterpriseCustomerConfiguration.all_objects.all()) == 2
        assert len(MoodleEnterpriseCustomerConfiguration.objects.all()) == 1

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_get(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
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
    def test_update_with_token(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
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
        self.assertEqual(self.moodle_config.decrypted_token, 'testing')
        self.assertEqual(self.moodle_config.decrypted_username, None)
        self.assertEqual(self.moodle_config.decrypted_password, None)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update_with_username_password(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        payload = {
            'moodle_base_url': 'http://testing2',
            'service_short_name': 'test',
            'enterprise_customer': ENTERPRISE_ID,
            'username': 'test_user',
            'password': 'test_pass'
        }
        response = self.client.put(url, payload)
        self.moodle_config.refresh_from_db()
        self.assertEqual(self.moodle_config.decrypted_username, 'test_user')
        self.assertEqual(self.moodle_config.decrypted_password, 'test_pass')
        self.assertEqual(self.moodle_config.decrypted_token, None)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_update_switch_from_token_to_username_password(self, mock_current_request):
        # First set token
        self.moodle_config.decrypted_token = 'initial_token'
        self.moodle_config.save()

        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        payload = {
            'username': 'new_user',
            'password': 'new_pass'
        }
        response = self.client.patch(url, payload)
        self.moodle_config.refresh_from_db()
        self.assertEqual(self.moodle_config.decrypted_username, 'new_user')
        self.assertEqual(self.moodle_config.decrypted_password, 'new_pass')
        self.assertEqual(self.moodle_config.decrypted_token, None)
        self.assertEqual(response.status_code, 200)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_credential_precedence_token_over_username_password(self, mock_current_request):
        """Test that when both token and username/password are provided, token takes precedence."""
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        payload = {
            'token': 'test_token',
            'username': 'test_user',
            'password': 'test_pass'
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, 200)

        # Verify that token is saved and username/password are cleared
        self.moodle_config.refresh_from_db()
        self.assertEqual(self.moodle_config.decrypted_token, 'test_token')
        self.assertIsNone(self.moodle_config.decrypted_username)
        self.assertIsNone(self.moodle_config.decrypted_password)

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_patch(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
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
            context=self.enterprise_customer.uuid,
        )
        url = reverse('api:v1:moodle:configuration-detail', args=[self.moodle_config.id])
        response = self.client.delete(url)
        configs = MoodleEnterpriseCustomerConfiguration.objects.filter()
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
        url = reverse('api:v1:moodle:configuration-list')

        self.moodle_config.moodle_base_url = 'gross'
        self.moodle_config.display_name = '!@#$%^&*(1889823456789#$%^&*('
        self.moodle_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        _, incorrect = data[0].get('is_valid')
        assert incorrect.get('incorrect') == ['moodle_base_url', 'display_name']

        self.moodle_config.decrypted_token = ''
        self.moodle_config.decrypted_username = ''
        self.moodle_config.decrypted_password = ''
        self.moodle_config.moodle_base_url = ''
        self.moodle_config.service_short_name = ''
        self.moodle_config.save()

        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, _ = data[0].get('is_valid')
        assert missing.get('missing') == ['moodle_base_url', 'token OR username and password', 'service_short_name']

        self.moodle_config.category_id = 10
        self.moodle_config.decrypted_username = 'lmao'
        self.moodle_config.decrypted_password = 'foobar'
        self.moodle_config.decrypted_token = 'baa'
        self.moodle_config.moodle_base_url = 'http://lovely.com'
        self.moodle_config.service_short_name = 'short'
        self.moodle_config.display_name = '1234!@#$'
        self.moodle_config.save()
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')
        missing, incorrect = data[0].get('is_valid')
        assert not missing.get('missing') and not incorrect.get('incorrect')
