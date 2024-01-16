"""
Tests for the Moodle content metadata transmitter.
"""

import unittest
from datetime import datetime
from unittest import mock

import responses
from pytest import mark

from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from integrated_channels.moodle.transmitters.content_metadata import MoodleContentMetadataTransmitter
from test_utils import factories


@mark.django_db
class TestMoodleContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``MoodleContentMetadataTransmitter``.
    """

    def setUp(self):
        super().setUp()
        self.moodle_base_url = 'http://testing/'
        self.api_token = 'token'
        self.password = 'pass'
        self.user = 'user'
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer
        )
        self.enterprise_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            moodle_base_url=self.moodle_base_url,
            enterprise_customer=enterprise_customer,
            username=self.user,
            password=self.password,
            token=self.api_token,
        )

    def test_prepare_items_for_transmission(self):
        channel_metadata_items = [
            {
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX',
                'content_type': 'course',
                'start': '2030-01-01T00:00:00Z',
                'end': '2030-03-01T00:00:00Z'
            },
        ]

        expected_prepared_items = {
            'courses[0][title]': 'edX Demonstration Course',
            'courses[0][key]': 'edX+DemoX',
            'courses[0][content_type]': 'course',
            'courses[0][start]': '2030-01-01T00:00:00Z',
            'courses[0][end]': '2030-03-01T00:00:00Z',
        }

        transmitter = MoodleContentMetadataTransmitter(self.enterprise_config)
        assert transmitter._prepare_items_for_transmission(channel_metadata_items) == expected_prepared_items  # pylint: disable=protected-access

    @responses.activate
    @mock.patch('integrated_channels.moodle.client.MoodleAPIClient.create_content_metadata')
    @mock.patch('integrated_channels.moodle.client.MoodleAPIClient.delete_content_metadata')
    @mock.patch('integrated_channels.moodle.client.MoodleAPIClient.update_content_metadata')
    def test_transmit_content_metadata_updates_records(
        self,
        create_content_metadata_mock,
        update_content_metadata_mock,
        delete_content_metadata_mock
    ):
        """
        Test that the Moodle content metadata transmitter generates and updates the appropriate content records as well
        as calls the Moodle API client for updates, deletes and creates.
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
            channel_metadata={},
            remote_created_at=datetime.utcnow(),
            remote_updated_at=None,
        )
        past_transmission_to_delete = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_2,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            remote_created_at=datetime.utcnow(),
            remote_deleted_at=None,
        )
        new_transmission_to_create = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_3,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            remote_created_at=None,
        )

        new_channel_metadata = {
            'title': 'edX Demonstration Course',
            'key': content_id_1,
            'content_type': 'course',
            'start': '2030-01-01T00:00:00Z',
            'end': '2030-03-01T00:00:00Z'
        }
        past_transmission_to_update.channel_metadata = new_channel_metadata

        create_content_metadata_mock.return_value = [200, 'OK']
        update_content_metadata_mock.return_value = [200, 'OK']
        delete_content_metadata_mock.return_value = [200, 'OK']

        transmitter = MoodleContentMetadataTransmitter(self.enterprise_config)
        create_payload = {
            content_id_3: new_transmission_to_create
        }
        update_payload = {
            content_id_1: past_transmission_to_update
        }
        delete_payload = {
            content_id_2: past_transmission_to_delete
        }
        transmitter.transmit(create_payload, update_payload, delete_payload)
        item_updated = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_1,
        ).first()
        assert item_updated.remote_updated_at
        assert item_updated.channel_metadata == new_channel_metadata
        item_deleted = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_2,
        ).first()
        assert item_deleted.remote_deleted_at
        item_created = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_3,
        ).first()
        assert item_created.remote_created_at
        assert create_content_metadata_mock.call_count == 1
        assert update_content_metadata_mock.call_count == 1
        assert delete_content_metadata_mock.call_count == 1
