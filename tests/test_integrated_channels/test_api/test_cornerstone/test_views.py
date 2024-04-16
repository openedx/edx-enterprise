"""
Tests for the `integrated_channels` Cornerstone configuration api.
"""
import json
from unittest import mock
from uuid import uuid4

from django.conf import settings
from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.utils import localized_utcnow
from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


class CornerstoneConfigurationViewSetTests(APITest):
    """
    Tests for CornerstoneConfigurationViewSet REST endpoints
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

        self.cornerstone_config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_soft_deleted_content_in_lists(self, mock_current_request):
        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )
        factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            deleted_at=localized_utcnow()
        )

        url = reverse('api:v1:cornerstone:configuration-list')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8')).get('results')

        assert len(data) == 1
        assert data[0]['id'] == self.cornerstone_config.id
        assert len(CornerstoneEnterpriseCustomerConfiguration.all_objects.all()) == 2
        assert len(CornerstoneEnterpriseCustomerConfiguration.objects.all()) == 1

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


class CornerstoneLearnerInformationViewTests(APITest):
    """
    Tests for CornerstoneLearnerInformationView API endpoints
    """
    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ENTERPRISE_ID)
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        self.csod_subdomain = 'dummy_subdomain'
        self.cornerstone_config = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            active=True,
            cornerstone_base_url=f'https://{self.csod_subdomain}.com',
        )
        self.cornerstone_config.save()
        self.course_key = 'edX+DemoX'
        self.path = settings.TEST_SERVER + '/integrated_channels/api/v1/cornerstone/save-learner-information'

    def test_save_learner_endpoint_happy_path(self):
        """
        Test the happy path where csod information for a learner gets saved successfully.
        """
        dummy_token = "123123123"
        post_data = {
            "courseKey": self.course_key,
            "enterpriseUUID": self.enterprise_customer.uuid,
            "userGuid": "24142313",
            "callbackUrl": "https://example.com/csod/callback/1",
            "sessionToken": dummy_token,
            "subdomain": self.csod_subdomain
        }
        response = self.client.post(self.path, post_data)
        assert response.status_code == 200
        self.cornerstone_config.refresh_from_db()
        assert self.cornerstone_config.session_token == dummy_token
        assert CornerstoneLearnerDataTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            course_id=self.course_key,
            user_id=self.user.id
        ).exists()

    def test_save_learner_endpoint_enterprise_customer_does_not_exist(self):
        """
        Test when enterprise customer does not exist.
        """
        dummy_token = "123123123"
        post_data = {
            "courseKey": self.course_key,
            "enterpriseUUID": 'invalid-uuid',
            "userGuid": "24142313",
            "callbackUrl": "https://example.com/csod/callback/1",
            "sessionToken": dummy_token,
            "subdomain": self.csod_subdomain
        }
        response = self.client.post(self.path, post_data)
        self.cornerstone_config.refresh_from_db()
        assert self.cornerstone_config.session_token != dummy_token
        assert response.status_code == 404
        assert CornerstoneLearnerDataTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            course_id=self.course_key,
            user_id=self.user.id
        ).count() == 0

    def test_save_learner_endpoint_cornerstone_config_does_not_exist(self):
        """
        Test when cornerstone config is not found.
        """
        dummy_token = "123123123"
        post_data = {
            "courseKey": self.course_key,
            "enterpriseUUID": self.enterprise_customer.uuid,
            "userGuid": "24142313",
            "callbackUrl": "https://example.com/csod/callback/1",
            "sessionToken": dummy_token,
            "subdomain": 'invalid-subdomain'
        }
        response = self.client.post(self.path, post_data)
        self.cornerstone_config.refresh_from_db()
        assert self.cornerstone_config.session_token != dummy_token
        assert response.status_code == 404
        assert CornerstoneLearnerDataTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            course_id=self.course_key,
            user_id=self.user.id
        ).count() == 0

    def test_save_learner_endpoint_learner_not_linked(self):
        """
        Test when learner is not linked to the given enterprise. We should not be saving anything in that case.
        """
        # Delete EnterpriseCustomerUser record.
        self.enterprise_customer_user.delete()
        dummy_token = "123123123"
        post_data = {
            "courseKey": self.course_key,
            "enterpriseUUID": self.enterprise_customer.uuid,
            "userGuid": "24142313",
            "callbackUrl": "https://example.com/csod/callback/1",
            "sessionToken": dummy_token,
            "subdomain": self.csod_subdomain
        }
        response = self.client.post(self.path, post_data)
        self.cornerstone_config.refresh_from_db()
        assert self.cornerstone_config.session_token != dummy_token
        assert response.status_code == 404
        assert CornerstoneLearnerDataTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            course_id=self.course_key,
            user_id=self.user.id
        ).count() == 0

    def test_save_learner_endpoint_update_existing_record(self):
        """
        When an existing transmisison record is found, we should update that one instead of creating a duplicate.
        """
        # Create transmission record
        CornerstoneLearnerDataTransmissionAudit.objects.create(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            user_id=self.user.id,
            course_id=self.course_key,
            session_token='123456'
        )
        dummy_token = "123123123"
        post_data = {
            "courseKey": self.course_key,
            "enterpriseUUID": self.enterprise_customer.uuid,
            "userGuid": "24142313",
            "callbackUrl": "https://example.com/csod/callback/1",
            "sessionToken": dummy_token,
            "subdomain": self.csod_subdomain
        }
        response = self.client.post(self.path, post_data)
        assert response.status_code == 200
        self.cornerstone_config.refresh_from_db()
        assert self.cornerstone_config.session_token == dummy_token
        assert CornerstoneLearnerDataTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.cornerstone_config.id,
            course_id=self.course_key,
            user_id=self.user.id
        ).count() == 1
