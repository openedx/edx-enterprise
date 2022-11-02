"""
Tests for the `integrated_channels` moodle configuration api.
"""
import datetime
from logging import getLogger
from unittest import mock

import ddt

from django.urls import reverse
from enterprise.constants import HTTP_STATUS_STRINGS

from test_utils import TEST_PASSWORD, APITest, factories

LOGGER = getLogger(__name__)


class ContentSyncStatusViewSetTests(APITest):
    """
    Tests for ContentSyncStatusViewSet REST endpoints
    """
    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        self.content_metadata_item = factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=400,
        )

        super().setUp()

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        if self.content_metadata_item:
            self.content_metadata_item.delete()
        if self.enterprise_customer_catalog:
            self.enterprise_customer_catalog.delete()
        super().tearDown()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_get(self):
        """
        tests a regular get with expected data
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.content_metadata_item.content_id == response_json['results'][0]['content_id']
        assert 'error' == response_json['results'][0]['sync_status']
        assert HTTP_STATUS_STRINGS.get(400) == response_json['results'][0]['friendly_status_message']

    def test_get_with_bad_channel_code(self):
        """
        tests that an invalid channel_code results in a 400
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = self.enterprise_customer_catalog.enterprise_customer.uuid
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'BROKEN',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        assert response.status_code == 400


@ddt.ddt
class LearnerSyncStatusViewSetTests(APITest):
    """
    Tests for LearnerSyncStatusViewSet REST endpoints
    """
    def setUp(self):
        self.generic_audit_1 = factories.GenericLearnerDataTransmissionAuditFactory()
        self.sap_audit_1 = factories.SapSuccessFactorsLearnerDataTransmissionAuditFactory()
        super().setUp()

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        if self.generic_audit_1:
            self.generic_audit_1.delete()
        if self.sap_audit_1:
            self.sap_audit_1.delete()
        super().tearDown()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_get_excludes_unneeded_fields(self):
        """
        tests a a get request will not return unneeded fields
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit_1.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit_1.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)

        # check that it excludes expected data
        assert "course_completed" not in response_json['results'][0].keys()
        assert "instructor_name" not in response_json['results'][0].keys()
        assert "course_id" not in response_json['results'][0].keys()

    def test_get(self):
        """
        tests a regular get with expected data
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit_1.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit_1.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.generic_audit_1.content_title == response_json['results'][0]['content_title']

        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.sap_audit_1.enterprise_customer_uuid,
                'integrated_channel_code': 'SAP',
                'plugin_configuration_id': self.sap_audit_1.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.sap_audit_1.content_title == response_json['results'][0]['content_title']
        assert self.sap_audit_1.user_email == response_json['results'][0]['user_email']

    @ddt.data((None, 'pending'), ('400', 'error'), ('200', 'okay'))
    @ddt.unpack
    def test_get_sync_statuses(self, audit_status, expected_sync_status):
        """
        tests learner data transmission audit API serializer sync status value based on transmission audit status
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit_1.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit_1.plugin_configuration_id
            }
        )
        self.generic_audit_1.status = audit_status
        self.generic_audit_1.save()
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        assert response_json['results'][0]['sync_status'] == expected_sync_status

    def test_get_with_bad_channel_code(self):
        """
        tests that an invalid channel_code results in a 400
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit_1.enterprise_customer_uuid,
                'integrated_channel_code': 'BROKEN',
                'plugin_configuration_id': self.generic_audit_1.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        assert response.status_code == 400
