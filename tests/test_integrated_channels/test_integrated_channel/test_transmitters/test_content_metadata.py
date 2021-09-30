# -*- coding: utf-8 -*-
"""
Tests for the base content metadata transmitter.
"""

import unittest
import uuid

import ddt
import mock
from pytest import mark

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataItemExport
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
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        # We need some non-abstract configuration for these things to work,
        # so it's okay for it to be any arbitrary channel. We randomly choose SAPSF.
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret",
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
        channel_metadata = {'update': True}
        payload = {
            content_id: ContentMetadataItemExport(
                {'key': content_id, 'content_type': 'course'},
                channel_metadata,
                uuid.uuid4()
            )
        }
        self.create_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

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
        payload = {
            content_id: ContentMetadataItemExport(
                {'key': content_id, 'content_type': 'course'},
                channel_metadata,
                uuid.uuid4()
            )
        }
        self.create_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

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
        ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata={}
        ).save()
        payload = {
            content_id: ContentMetadataItemExport(
                {'key': content_id, 'content_type': 'course'},
                channel_metadata,
                uuid.uuid4()
            )
        }
        self.update_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

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
        payload = {
            content_id: ContentMetadataItemExport(
                {'key': content_id, 'content_type': 'course'},
                channel_metadata,
                uuid.uuid4()
            )
        }
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_not_called()

    def test_transmit_update_failure(self):
        """
        Test unsuccessful update of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata={}
        ).save()
        payload = {
            content_id: ContentMetadataItemExport(
                {'key': content_id, 'content_type': 'course'},
                channel_metadata,
                uuid.uuid4()
            )
        }
        self.update_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_called()
        self.delete_content_metadata_mock.assert_not_called()

        updated_transmission = ContentMetadataItemTransmission.objects.get(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

        assert updated_transmission.channel_metadata == {}

    def test_transmit_delete_success(self):
        """
        Test successful deletion of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        ).save()
        payload = {}
        self.delete_content_metadata_mock.return_value = (200, '{"success":"true"}')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        assert not ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )

    def test_transmit_delete_failure(self):
        """
        Test successful deletion of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        channel_metadata = {'update': True}
        ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
            channel_metadata=channel_metadata
        ).save()
        payload = {}
        self.delete_content_metadata_mock.side_effect = ClientError('error occurred')
        transmitter = ContentMetadataTransmitter(self.enterprise_config)
        transmitter.transmit(payload)

        self.create_content_metadata_mock.assert_not_called()
        self.update_content_metadata_mock.assert_not_called()
        self.delete_content_metadata_mock.assert_called()

        assert ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_id=content_id,
        )
