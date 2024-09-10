"""
Tests for the base content metadata transmitter.
"""

import unittest
import uuid
from datetime import datetime
from unittest import mock

import ddt
import requests
from pytest import mark

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``ContentMetadataTransmitter``.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        # We need some non-abstract configuration for these things to work,
        # so it's okay for it to be any arbitrary channel. We randomly choose SAPSF.
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            decrypted_key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            decrypted_secret="client_secret",
            transmission_chunk_size=5,
        )
        self.enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer
        )
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()

        self.success_response_code = 200
        self.success_response_body = '{"success":"true"}'

        # Mocks
        create_content_metadata_mock = mock.patch(
            'integrated_channels.integrated_channel.client.IntegratedChannelApiClient.create_content_metadata'
        )
        self.create_content_metadata_mock = create_content_metadata_mock.start()
        self.addCleanup(create_content_metadata_mock.stop)

        update_content_metadata_mock = mock.patch(
            'integrated_channels.integrated_channel.client.IntegratedChannelApiClient.update_content_metadata'
        )
        self.update_content_metadata_mock = update_content_metadata_mock.start()
        self.addCleanup(update_content_metadata_mock.stop)

        delete_content_metadata_mock = mock.patch(
            'integrated_channels.integrated_channel.client.IntegratedChannelApiClient.delete_content_metadata'
        )
        self.delete_content_metadata_mock = delete_content_metadata_mock.start()
        self.addCleanup(delete_content_metadata_mock.stop)

    def test_transmit_create_success(self):
        """
        Test successful creation of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        content_id_2 = 'course:DemoX2'

        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        content_2 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_2,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        create_payload = {
            content_id_1: content_1,
            content_id_2: content_2,
        }
        update_payload = {}
        delete_payload = {}

        self.create_content_metadata_mock.return_value = (self.success_response_code, self.success_response_body)
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        created_transmission_1 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        created_transmission_2 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_2,
        )

        assert created_transmission_1.remote_created_at is not None
        assert created_transmission_1.api_record.status_code == self.success_response_code
        assert created_transmission_1.api_record.body == self.success_response_body

        assert created_transmission_2.remote_created_at is not None
        assert created_transmission_2.api_record.status_code == self.success_response_code
        assert created_transmission_2.api_record.body == self.success_response_body

    def test_transmit_create_failure(self):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        content_id_2 = 'course:DemoX2'

        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        content_2 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_2,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        create_payload = {
            content_id_1: content_1,
            content_id_2: content_2,
        }
        update_payload = {}
        delete_payload = {}
        self.create_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        created_transmission_1 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        created_transmission_2 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_2,
        )

        assert created_transmission_1.remote_created_at is not None
        assert created_transmission_1.api_response_status_code > 400
        assert created_transmission_1.api_record.status_code > 400
        assert created_transmission_1.api_record.body == 'error occurred'

        assert created_transmission_2.remote_created_at is not None
        assert created_transmission_2.api_response_status_code > 400
        assert created_transmission_2.api_record.status_code > 400
        assert created_transmission_2.api_record.body == 'error occurred'

    def test_transmit_create_exception_failure(self):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'

        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        create_payload = {
            content_id_1: content_1,
        }
        update_payload = {}
        delete_payload = {}
        self.create_content_metadata_mock.side_effect = Exception('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        created_transmission_1 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert created_transmission_1.remote_created_at is not None
        assert created_transmission_1.api_response_status_code == 555
        assert created_transmission_1.api_record.status_code == 555
        assert created_transmission_1.api_record.body == 'error occurred'

    def test_transmit_create_request_exception_failure(self):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'

        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata={}
        )

        create_payload = {
            content_id_1: content_1,
        }
        update_payload = {}
        delete_payload = {}
        self.create_content_metadata_mock.side_effect = requests.exceptions.ConnectionError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        created_transmission_1 = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert created_transmission_1.remote_created_at is not None
        assert created_transmission_1.api_response_status_code == 555
        assert created_transmission_1.api_record.status_code == 555
        assert created_transmission_1.api_record.body == 'error occurred'

    def test_transmit_update_success(self):
        """
        Test successful update of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )
        create_payload = {}
        update_payload = {content_id_1: content_1}
        delete_payload = {}

        self.update_content_metadata_mock.return_value = (self.success_response_code, self.success_response_body)
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_called()
        self.delete_content_metadata_mock.assert_not_called()

        updated_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert updated_transmission.remote_updated_at is not None
        assert updated_transmission.api_response_status_code == self.success_response_code
        assert updated_transmission.api_record.status_code == self.success_response_code
        assert updated_transmission.api_record.body == self.success_response_body

    def test_transmit_update_not_needed(self):
        """
        Test successful update of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )
        create_payload = {}
        update_payload = {}
        delete_payload = {}
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

    def test_transmit_update_failure(self):
        """
        Test unsuccessful update of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )
        create_payload = {}
        update_payload = {content_id_1: content_1}
        delete_payload = {}
        self.update_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_called()
        self.delete_content_metadata_mock.assert_not_called()

        updated_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert updated_transmission.remote_updated_at is not None
        assert updated_transmission.api_response_status_code > 400
        assert updated_transmission.api_record.status_code > 400
        assert updated_transmission.api_record.body == 'error occurred'

    @mark.django_db
    @ddt.ddt
    def test_transmit_delete_success(self):
        """
        Test successful deletion of content metadata during transmission.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id_1: content_1}
        self.delete_content_metadata_mock.return_value = (self.success_response_code, self.success_response_body)
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        deleted_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert deleted_transmission.remote_deleted_at is not None
        assert deleted_transmission.api_response_status_code == self.success_response_code
        assert deleted_transmission.api_record.status_code == self.success_response_code
        assert deleted_transmission.api_record.body == self.success_response_body

    def test_transmit_delete_failure(self):
        """
        Test that a failure during deletion of content metadata during transmission will not update records.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id_1: content_1}
        self.delete_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        deleted_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id_1,
        )

        assert deleted_transmission.remote_deleted_at is not None
        assert deleted_transmission.api_record.status_code > 400
        assert deleted_transmission.api_record.body == 'error occurred'

    @mark.django_db
    @ddt.ddt
    def test_transmit_success_resolve_orphaned_content(self):
        """
        Test that a successful transmission will resolve orphaned content.
        """
        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )
        orphaned_content_record = factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code=self.enterprise_config.channel_code(),
            plugin_configuration_id=self.enterprise_config.id,
            content_id=content_1.content_id,
            transmission=content_1,
        )

        assert not orphaned_content_record.resolved

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id_1: content_1}
        self.delete_content_metadata_mock.return_value = (self.success_response_code, self.success_response_body)
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        orphaned_content_record.refresh_from_db()
        assert orphaned_content_record.resolved

    def test_content_data_transmission_dry_run_mode(self):
        """
        Test that a customer's configuration can run in dry run mode
        """
        # Set feature flag to true
        self.enterprise_config.dry_run_mode_enabled = True

        content_id_1 = 'course:DemoX'
        channel_metadata_1 = {'update': True}
        content_1 = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            channel_metadata=channel_metadata_1,
            remote_created_at=datetime.utcnow()
        )

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id_1: content_1}
        self.delete_content_metadata_mock.return_value = (self.success_response_code, self.success_response_body)
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload)

        # with dry_run_mode_enabled = True we shouldn't be able to call these methods
        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()
