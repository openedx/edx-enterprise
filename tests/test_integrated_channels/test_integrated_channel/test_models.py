"""
Tests for the integrated channel models.
"""

import datetime
import unittest
from unittest import mock

from pytest import mark

from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.models import ApiResponseRecord, ContentMetadataItemTransmission
from test_utils import factories
from test_utils.fake_catalog_api import FAKE_COURSE_RUN, get_fake_catalog, get_fake_content_metadata
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestContentMetadataItemTransmission(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``ContentMetadataItemTransmission`` model.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory(
                enterprise_customer=self.enterprise_customer,
            )

        self.config = factories.GenericEnterpriseCustomerPluginConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        self.fake_catalog = get_fake_catalog()
        self.fake_catalog_modified_at = max(
            self.fake_catalog['content_last_modified'], self.fake_catalog['catalog_modified']
        )
        self.fake_catalogs_last_modified = {
            get_content_metadata_item_id(
                content_metadata
            ): self.fake_catalog_modified_at for content_metadata in get_fake_content_metadata()
        }
        super().setUp()

    def test_content_meta_data_string_representation(self):
        """
        Test the string representation of the model.
        """
        integrated_channel_code = 'test-channel-code'
        content_id = 'test-course'
        expected_string = '<Content item {content_id} for Customer {customer} with Channel {channel}>'.format(
            content_id=content_id,
            customer=self.enterprise_customer,
            channel=integrated_channel_code
        )
        transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_customer,
            integrated_channel_code=integrated_channel_code,
            content_id=content_id
        )
        assert expected_string == repr(transmission)

    def test_failed_delete_transmissions_getter(self):
        """
        Test that we properly find created but unsent transmission audit items
        """
        api_record = ApiResponseRecord(status_code=500, body='ERROR')
        api_record.save()
        deleted_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=None,
            remote_deleted_at=datetime.datetime.utcnow(),
            api_response_status_code=500,
            api_record=api_record,
        )
        deleted_transmission.save()
        found_item = ContentMetadataItemTransmission.incomplete_delete_transmissions(
            self.enterprise_customer,
            self.config.id,
            self.config.channel_code(),
            FAKE_COURSE_RUN['key'],
        ).first()
        assert found_item == deleted_transmission

    def test_failed_update_transmissions_getter(self):
        """
        Test that we properly find created but unsent transmission audit items
        """
        api_record = ApiResponseRecord(status_code=500, body='ERROR')
        api_record.save()
        updated_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            remote_deleted_at=None,
            api_response_status_code=500,
            api_record=api_record,
        )
        updated_transmission.save()
        found_item = ContentMetadataItemTransmission.incomplete_update_transmissions(
            self.enterprise_customer,
            self.config.id,
            self.config.channel_code(),
            FAKE_COURSE_RUN['key'],
        ).first()
        assert found_item == updated_transmission

    def test_incomplete_create_transmissions_getter(self):
        """
        Test that we properly find created but unsent transmission audit items
        """
        incomplete_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=None,
            remote_updated_at=None,
            remote_deleted_at=None,
        )
        incomplete_transmission.save()
        found_item = ContentMetadataItemTransmission.incomplete_create_transmissions(
            self.enterprise_customer,
            self.config.id,
            self.config.channel_code(),
            FAKE_COURSE_RUN['key'],
        ).first()
        assert found_item == incomplete_transmission

    def test_failed_incomplete_create_transmissions_getter(self):
        """
        Test that we properly find created and attempted but unsuccessful transmission audit items
        """
        api_record = ApiResponseRecord(status_code=500, body='ERROR')
        api_record.save()
        failed_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=None,
            remote_deleted_at=None,
            api_response_status_code=500,
            api_record=api_record,
        )
        failed_transmission.save()
        found_item = ContentMetadataItemTransmission.incomplete_create_transmissions(
            self.enterprise_customer,
            self.config.id,
            self.config.channel_code(),
            FAKE_COURSE_RUN['key'],
        ).first()
        assert found_item == failed_transmission
