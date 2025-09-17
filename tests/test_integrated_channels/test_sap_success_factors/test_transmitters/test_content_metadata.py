"""
Tests for the SAP SuccessFactors content metadata transmitter.
"""

import json
import unittest
from datetime import datetime
from unittest import mock

import responses
from pytest import mark

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
            decrypted_key='client_id',
            sapsf_base_url=self.url_base,
            sapsf_company_id='company_id',
            sapsf_user_id='user_id',
            decrypted_secret='client_secret',
        )
        factories.SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path=self.completion_status_api_path,
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path
        )

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_content_metadata')
    def test_transmit_create_failure(self, create_content_metadata_mock):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id = 'course:DemoX'

        # Set the chunk size to 1 to simulate 2 network calls
        self.enterprise_config.transmission_chunk_size = 1
        self.enterprise_config.save()
        create_content_metadata_mock.side_effect = ClientError('error occurred')
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)

        new_transmission_to_create = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id,
            enterprise_customer=self.enterprise_config.enterprise_customer,
            plugin_configuration_id=self.enterprise_config.id,
            integrated_channel_code=self.enterprise_config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            channel_metadata={},
            remote_created_at=None,
        )

        create_payload = {
            content_id: new_transmission_to_create,
        }
        update_payload = {}
        delete_payload = {}
        transmitter.transmit(create_payload, update_payload, delete_payload)

        item_created = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id,
        ).first()
        assert item_created.remote_created_at
        assert item_created.api_response_status_code >= 400

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_content_metadata')
    def test_transmit_api_usage_limit(self, create_content_metadata_mock):
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

        create_content_metadata_mock.return_value = [200, 'OK']
        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        settings_with_limits = {self.enterprise_config.channel_code(): 1}
        with override_settings(INTEGRATED_CHANNELS_API_CHUNK_TRANSMISSION_LIMIT=settings_with_limits):
            new_transmission_to_create = factories.ContentMetadataItemTransmissionFactory(
                content_id=content_id,
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_last_changed='2021-07-16T15:11:10.521611Z',
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                channel_metadata={},
                remote_created_at=None,
            )
            new_transmission_to_create_2 = factories.ContentMetadataItemTransmissionFactory(
                content_id=content_id_2,
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_last_changed='2021-07-16T15:11:10.521611Z',
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                channel_metadata={},
                remote_created_at=None,
            )

            create_payload = {
                content_id: new_transmission_to_create,
                content_id_2: new_transmission_to_create_2,
            }
            update_payload = {}
            delete_payload = {}

            transmitter.transmit(create_payload, update_payload, delete_payload)

            assert create_content_metadata_mock.call_count == 1

            item_created = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                content_id=content_id,
            ).first()
            assert item_created.remote_created_at

            item_not_created = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                content_id=content_id_2,
            ).first()
            assert not item_not_created.remote_created_at

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.delete_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_content_metadata')
    def test_transmit_content_metadata_updates_records(
        self,
        create_content_metadata_mock,
        update_content_metadata_mock,
        delete_content_metadata_mock
    ):
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
            channel_metadata={},
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

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
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
        item_deleted = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_2,
        ).first()
        assert item_deleted.remote_deleted_at

        assert delete_content_metadata_mock.call_count == 1
        assert create_content_metadata_mock.call_count == 0
        assert update_content_metadata_mock.call_count == 0

        transmitter.transmit(create_payload, update_payload, {})
        item_updated = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_1,
        ).first()
        assert item_updated.remote_updated_at
        assert item_updated.channel_metadata == new_channel_metadata
        assert update_content_metadata_mock.call_count == 1

        transmitter.transmit(create_payload, {}, {})
        item_created = ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            content_id=content_id_3,
        ).first()
        assert item_created.remote_created_at
        assert create_content_metadata_mock.call_count == 1

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_content_metadata')
    def test_transmit_api_usage_limit_disabled(self, create_content_metadata_mock):
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
            new_transmission_to_create = factories.ContentMetadataItemTransmissionFactory(
                content_id=content_id,
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_last_changed='2021-07-16T15:11:10.521611Z',
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                channel_metadata={},
                remote_created_at=None,
            )
            new_transmission_to_create_2 = factories.ContentMetadataItemTransmissionFactory(
                content_id=content_id_2,
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_last_changed='2021-07-16T15:11:10.521611Z',
                enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
                channel_metadata={},
                remote_created_at=None,
            )

            create_payload = {
                content_id: new_transmission_to_create,
                content_id_2: new_transmission_to_create_2,
            }
            update_payload = {}
            delete_payload = {}

            create_content_metadata_mock.return_value = [200, 'OK']
            transmitter.transmit(create_payload, update_payload, delete_payload)
            assert create_content_metadata_mock.call_count == 2

            assert ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_config.enterprise_customer,
                plugin_configuration_id=self.enterprise_config.id,
                integrated_channel_code=self.enterprise_config.channel_code(),
            ).count() == 2

    @mock.patch('integrated_channels.utils.LOGGER')
    def test_filter_api_response_successful(self, logger_mock):
        """
        Test that the api response is successfully filtered
        """
        response = '{"ocnCourses": [{"courseID": "course:DemoX"}, {"courseID": "course:DemoX2"}]}'
        content_id = 'course:DemoX'

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        # pylint: disable=protected-access
        filtered_response = transmitter._filter_api_response(response, content_id)

        assert json.loads(filtered_response) == {"ocnCourses": [{"courseID": "course:DemoX"}]}
        assert logger_mock.exception.call_count == 0

    @mock.patch('integrated_channels.logger.log_with_context')
    def test_filter_api_response_exception(self, logger_mock):
        """
        Test that the api response is not filtered if an exception occurs
        """
        response = 'Invalid JSON response'
        content_id = 'course:DemoX'

        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        # pylint: disable=protected-access
        filtered_response = transmitter._filter_api_response(response, content_id)

        assert filtered_response == response
        logger_mock.assert_called_once()
