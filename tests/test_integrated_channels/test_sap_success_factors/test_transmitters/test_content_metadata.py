"""
Tests for the SAP SuccessFactors content metadata transmitter.
"""

import logging
import unittest
import uuid
from datetime import datetime
from unittest import mock

import responses
from pytest import mark
from testfixtures import LogCapture

from django.test.utils import override_settings

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from integrated_channels.sap_success_factors.transmitters.content_metadata import (
    SapSuccessFactorsContentMetadataTransmitter,
)
from test_utils import factories


@mark.django_db
class TestSapSuccessFactorsContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``SapSuccessFactorsContentMetadataTransmitter``.
    """

    def setUp(self):
        super().setUp()
        self.url_base = 'http://test.successfactors.com/'
        self.oauth_api_path = 'learning/oauth-api/rest/v1/token'
        self.completion_status_api_path = 'learning/odatav4/public/admin/ocn/v1/current-user/item/learning-event'
        self.course_api_path = 'learning/odatav4/public/admin/ocn/v1/OcnCourses'
        self.expires_in = 1800
        self.access_token = 'access_token'
        self.expected_token_response_body = {'expires_in': self.expires_in, 'access_token': self.access_token}
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer
        )
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key='client_id',
            sapsf_base_url=self.url_base,
            sapsf_company_id='company_id',
            sapsf_user_id='user_id',
            secret='client_secret',
        )
        factories.SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path=self.completion_status_api_path,
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path
        )

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_create_failure(self, update_content_metadata_mock):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        content_id_2 = 'course:DemoX2'

        # Set the chunk size to 1 to simulate 2 network calls
        self.enterprise_config.transmission_chunk_size = 1
        self.enterprise_config.save()
        update_content_metadata_mock.side_effect = ClientError('error occurred')
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        with LogCapture(level=logging.ERROR) as log_capture:
            transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)

            create_payload = {
                content_id: {'courseID': content_id, 'update': True},
                content_id_2: {'courseID': content_id_2, 'update': True},
            }
            update_payload = {}
            delete_paylaod = {}
            content_updated_mapping = {
                content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
                content_id_2: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()}
            }
            transmitter.transmit(create_payload, update_payload, delete_paylaod, content_updated_mapping)

            assert len(log_capture.records) == 2
            assert 'Failed to update [1] content metadata items' in log_capture.records[0].getMessage()
            assert not ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_id=content_id,
            ).exists()

            assert not ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_id=content_id_2,
            ).exists()

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_api_usage_limit(self, update_content_metadata_mock):
        """
        Test that API usage limit is being observed while transmitting content metadata.
        """
        content_id = 'course:DemoX'
        content_id_2 = 'course:DemoX2'

        # Set the chunk size to 1 to simulate 2 network calls
        self.enterprise_config.transmission_chunk_size = 1
        self.enterprise_config.save()
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        create_payload = {
            content_id: {'courseID': content_id, 'update': True},
            content_id_2: {'courseID': content_id_2, 'update': True},
        }
        update_payload = {}
        delete_payload = {}

        content_updated_mapping = {
            content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
            content_id_2: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()}
        }

        transmitter.transmit(create_payload, update_payload, delete_payload, content_updated_mapping)

        assert update_content_metadata_mock.call_count == 1

        assert ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
        ).count() == 1

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_content_metadata_updates_records(self, update_content_metadata_mock):
        """
        Test that the sap transmitter will call the client updated method with both create and update data as well as
        save/update all appropriate records.
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

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
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
            plugin_configuration_id=self.enterprise_config.id,
            content_id=content_id_1,
        ).first()
        assert item_updated.channel_metadata == new_channel_metadata
        item_deleted = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            plugin_configuration_id=self.enterprise_config.id,
            content_id=content_id_2,
        ).first()
        assert item_deleted.deleted_at
        item_created = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            plugin_configuration_id=self.enterprise_config.id,
            content_id=content_id_3,
        ).first()
        assert item_created.channel_metadata == {'courseID': 'something_new'}
        assert update_content_metadata_mock.call_count == 1

        prepared_delete_data = past_transmission_to_delete.channel_metadata
        prepared_delete_data['status'] = 'INACTIVE'
        assert update_content_metadata_mock.call_args[0][0] == transmitter._serialize_items(  # pylint: disable=protected-access
            [{'courseID': 'something_new'}, new_channel_metadata, prepared_delete_data]
        )

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_api_usage_limit_disabled(self, update_content_metadata_mock):
        """
        Test that API usage limit is not applied if setting is not present.
        """
        content_id = 'course:DemoX'
        content_id_2 = 'course:DemoX2'

        # Set the chunk size to 1 to simulate 2 network calls
        self.enterprise_config.transmission_chunk_size = 1
        self.enterprise_config.save()
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)

        with override_settings(INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT={}):
            create_payload = {
                content_id: {'courseID': content_id, 'update': True},
                content_id_2: {'courseID': content_id_2, 'update': True},
            }
            update_payload = {}
            delete_paylaod = {}

            content_updated_mapping = {
                content_id: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()},
                content_id_2: {'catalog_uuid': uuid.uuid4(), 'modified': datetime.now()}
            }

            transmitter.transmit(create_payload, update_payload, delete_paylaod, content_updated_mapping)
            assert update_content_metadata_mock.call_count == 2

            assert ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
            ).count() == 2

    @responses.activate
    def test_prepare_items_for_delete(self):
        """
        Test items to be deleted are updated with a status of INACTIVE.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )
        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        items_to_delete = {'test': {}}
        transmitter._prepare_items_for_delete(items_to_delete)  # pylint: disable=protected-access
        assert items_to_delete['test']['status'] == 'INACTIVE'
