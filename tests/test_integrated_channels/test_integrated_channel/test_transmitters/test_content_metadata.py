"""
Tests for the base content metadata transmitter.
"""

import unittest
import uuid
from datetime import datetime
from unittest import mock

import ddt
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
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret",
        )
        self.enterprise_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer
        )
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()

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
        content_id = 'course:DemoX'
        content_id_2 = 'course:DemoX2'
        channel_metadata = {'update': True}
        create_payload = {
            content_id: channel_metadata,
            content_id_2: channel_metadata,
        }
        update_payload = {}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
            content_id_2: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()}
        }
        self.create_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        created_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

        assert created_transmission.channel_metadata == channel_metadata

    def test_transmit_create_failure(self):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        create_payload = {content_id: channel_metadata}
        update_payload = {}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }
        self.create_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

        assert not ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

    def test_transmit_update_success(self):
        """
        Test successful update of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata={}
        )
        past_transmission.save()

        past_transmission.channel_metadata = channel_metadata
        create_payload = {}
        update_payload = {content_id: past_transmission}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }

        self.update_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_called()
        self.delete_content_metadata_mock.assert_not_called()

        updated_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

        assert updated_transmission.channel_metadata == channel_metadata

    def test_transmit_update_not_needed(self):
        """
        Test successful update of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        ).save()
        create_payload = {}
        update_payload = {}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

    def test_transmit_update_failure(self):
        """
        Test unsuccessful update of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata={}
        )
        past_transmission.save()
        create_payload = {}
        update_payload = {content_id: past_transmission}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }
        self.update_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_called()
        self.delete_content_metadata_mock.assert_not_called()

        updated_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

        assert updated_transmission.channel_metadata == {}

    @mark.django_db
    @ddt.ddt
    def test_transmit_delete_success(self):
        """
        Test successful deletion of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        )
        past_transmission.save()

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id: past_transmission}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }
        self.delete_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        assert ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        ).first().deleted_at

    def test_transmit_delete_failure(self):
        """
        Test that a failure during deletion of content metadata during transmission will not update records.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        )
        past_transmission.save()

        create_payload = {}
        update_payload = {}
        delete_payload = {content_id: past_transmission}
        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
        }
        self.delete_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        assert not ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        ).first().deleted_at

    @mark.django_db
    @ddt.ddt
    def test_transmitting_create_content_with_previously_deleted_record(self):
        """
        Test that records associated with content that was transmitted under a different catalog will be converted to
        the new catalog
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata,
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid,
            deleted_at=datetime.now()
        )
        past_transmission.save()
        create_payload = {content_id: channel_metadata}
        update_payload = {}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': self.enterprise_catalog.uuid, 'modified': datetime.now()},
        }
        self.create_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        assert past_transmission.deleted_at
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)
        past_transmission.refresh_from_db()
        assert not past_transmission.deleted_at

    @mark.django_db
    @ddt.ddt
    def test_transmitting_same_content_over_different_catalogs(self):
        """
        Test that records associated with content that was transmitted under a different catalog will be converted to
        the new catalog
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata,
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid
        )
        past_transmission.save()

        new_catalog_uuid = uuid.uuid4()

        create_payload = {content_id: channel_metadata}
        update_payload = {}
        delete_payload = {}
        content_updated_mapping = {
            content_id: {'catalog_uuid': new_catalog_uuid, 'modified': datetime.now()},
        }
        self.create_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)
        assert not ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_catalog.uuid
        ).first()
        assert ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=new_catalog_uuid
        ).first()
