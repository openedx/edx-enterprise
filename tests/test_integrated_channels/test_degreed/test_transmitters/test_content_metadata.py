"""
Tests for the Degreed content metadata transmitter.
"""

import unittest
from datetime import datetime
from unittest import mock

import responses
from pytest import mark

from integrated_channels.degreed.transmitters.content_metadata import DegreedContentMetadataTransmitter
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import factories


@mark.django_db
class TestDegreedContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``DegreedContentMetadataTransmitter``.
    """

    def setUp(self):
        super().setUp()
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer
        )
        self.enterprise_config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer
        )

    @responses.activate
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.create_content_metadata')
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.delete_content_metadata')
    @mock.patch('integrated_channels.degreed.client.DegreedAPIClient.update_content_metadata')
    def test_transmit_content_metadata_updates_records(
        self,
        create_content_metadata_mock,
        update_content_metadata_mock,
        delete_content_metadata_mock
    ):
        """
        Test that the Degreed content metadata transmitter generates and updates the appropriate content records as well
        as calls the Degreed API client for updates, deletes and creates.
        """
        self.enterprise_config.transmission_chunk_size = 3
        self.enterprise_config.save()
        content_id_1 = 'content_id_1'
        content_id_2 = 'content_id_2'
        content_id_3 = 'content_id_3'
        past_transmission_to_update = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_1,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            channel_metadata={}
        )
        past_transmission_to_delete = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_2,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid
        )

        new_channel_metadata = {
            'title': 'edX Demonstration Course',
            'key': content_id_1,
            'content_type': 'course',
            'start': '2030-01-01T00:00:00Z',
            'end': '2030-03-01T00:00:00Z'
        }
        past_transmission_to_update.channel_metadata = new_channel_metadata

        transmitter = DegreedContentMetadataTransmitter(self.enterprise_config)
        content_updated_mapping = {
            content_id_1: {'modified': datetime.now(), 'catalog_uuid': self.enterprise_customer_catalog.uuid},
            content_id_2: {'modified': datetime.now(), 'catalog_uuid': self.enterprise_customer_catalog.uuid},
            content_id_3: {'modified': datetime.now(), 'catalog_uuid': self.enterprise_customer_catalog.uuid}
        }
        create_payload = {
            content_id_3: {'courseID': 'something_new'}
        }
        update_payload = {
            content_id_1: past_transmission_to_update
        }
        delete_payload = {
            content_id_2: past_transmission_to_delete
        }
        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)
        item_updated = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_1,
        ).first()
        assert item_updated.channel_metadata == new_channel_metadata
        item_deleted = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_2,
        ).first()
        assert item_deleted.deleted_at
        item_created = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_3,
        ).first()
        assert item_created.channel_metadata == {'courseID': 'something_new'}
        assert create_content_metadata_mock.call_count == 1
        assert update_content_metadata_mock.call_count == 1
        assert delete_content_metadata_mock.call_count == 1
