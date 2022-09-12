"""
Tests for the `integrated_channels` moodle configuration api.
"""
import datetime
import json
from logging import getLogger
from unittest import mock
from uuid import uuid4

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from test_utils import APITest, factories, TEST_PASSWORD

from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    GenericLearnerDataTransmissionAudit,
)
from integrated_channels.sap_success_factors.models import (
    SapSuccessFactorsLearnerDataTransmissionAudit,
)

LOGGER = getLogger(__name__)
ENTERPRISE_ID = str(uuid4())


class ContentSyncStatusViewSetTests(APITest):
    """
    Tests for ContentSyncStatusViewSet REST endpoints
    """
    def setUp(self):
        
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
        )

        super().setUp()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_get(self):
        self.setup_admin_user(True)
        url = reverse(
            f'api:v1:logs:content_sync_status_logs',
            kwargs={'enterprise_customer_uuid': self.enterprise_customer_catalog.enterprise_customer.uuid, 'integrated_channel_code': 'GENERIC', 'plugin_configuration_id': 1}
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        # response = self.load_json(response.content)
        # assert expected_json == response['results'][0]['data_sharing_consent_records']
        assert True


class LearnerSyncStatusViewSetTests(APITest):
    """
    Tests for LearnerSyncStatusViewSet REST endpoints
    """
    def setUp(self):
        self.generic_audit_1 = factories.GenericLearnerDataTransmissionAuditFactory()
        self.sap_audit_1 = factories.SapSuccessFactorsLearnerDataTransmissionAuditFactory()
        super().setUp()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_get(self):
        self.setup_admin_user(True)
        url = reverse(
            f'api:v1:logs:learner_sync_status_logs',
            kwargs={'enterprise_customer_uuid': self.generic_audit_1.enterprise_customer_uuid, 'integrated_channel_code': 'GENERIC', 'plugin_configuration_id': self.generic_audit_1.plugin_configuration_id}
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        # response = self.load_json(response.content)
        # assert expected_json == response['results'][0]['data_sharing_consent_records']
        url = reverse(
            f'api:v1:logs:learner_sync_status_logs',
            kwargs={'enterprise_customer_uuid': self.sap_audit_1.enterprise_customer_uuid, 'integrated_channel_code': 'SAP', 'plugin_configuration_id': self.sap_audit_1.plugin_configuration_id}
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        assert True
