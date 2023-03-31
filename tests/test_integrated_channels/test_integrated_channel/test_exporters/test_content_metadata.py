"""
Tests for the base content metadata exporter.
"""

import datetime
import logging
import unittest
from collections import OrderedDict
from unittest import mock

from pytest import mark
from testfixtures import LogCapture

from django.test.utils import override_settings

from enterprise.constants import EXEC_ED_COURSE_TYPE
from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import FAKE_UUIDS, factories
from test_utils.factories import ContentMetadataItemTransmissionFactory
from test_utils.fake_catalog_api import (
    FAKE_COURSE,
    FAKE_COURSE_RUN,
    FAKE_COURSE_RUN2,
    get_fake_catalog,
    get_fake_catalog_diff_create,
    get_fake_content_metadata,
)
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``ContentMetadataExporter`` class.
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
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

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_create_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not delete_payload

        assert mock_get_content_metadata.get(FAKE_COURSE_RUN['key'])

        for key in create_payload:
            assert key in ['edX+DemoX', 'course-v1:edX+DemoX+Demo_Course', FAKE_UUIDS[3]]

        cmit = ContentMetadataItemTransmission.objects.get(content_id=FAKE_COURSE['key'])
        assert cmit.content_title is not None

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_tags_exec_ed_content(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        mock_exec_ed_content = get_fake_content_metadata()

        # make the first course and only the first course of type exec ed
        mock_exec_ed_content[0]['content_type'] = 'course'
        mock_exec_ed_content[0]['course_type'] = EXEC_ED_COURSE_TYPE
        mock_get_content_metadata.return_value = mock_exec_ed_content
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not delete_payload

        # Assert that only the exec ed content has been tagged
        assert "ExecEd:" in create_payload[mock_exec_ed_content[0]['key']].content_title
        assert "ExecEd:" not in create_payload[mock_exec_ed_content[1]['key']].content_title

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_with_overlapping_content(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        Test that the content metadata exporter will check the diff request `create` payload for any already existing
        transmission audits and exclude those from the create payload
        """
        content_1 = 'course-v1:edX+DemoX+Demo_Course'
        content_2 = 'edX+DemoX'

        # Double check that neither of these values exists as transmission audits yet
        assert not ContentMetadataItemTransmission.objects.filter(content_id__in=[content_1, content_2])

        # Create one
        ContentMetadataItemTransmissionFactory(
            content_id=content_1,
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            remote_created_at=datetime.datetime.utcnow(),
        )

        mock_get_content_metadata.return_value = get_fake_content_metadata()
        # Mock that the catalog service reports we need to create both pieces of content
        mock_get_catalog_diff.return_value = (
            [{'content_key': content_1}, {'content_key': content_2}], [], []
        )
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        # Assert that the exporter detects the already existing content, and excludes it from the create payload
        assert len(create_payload) == 1
        assert len(update_payload) == 0
        assert len(delete_payload) == 0

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_delete_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a delete payload of the course data when retrieving catalog
        diffs with content to delete.
        """
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission.save()
        mock_create_items = []
        mock_delete_items = [{'content_key': FAKE_COURSE_RUN['key']}]
        mock_matched_items = []
        mock_get_catalog_diff.return_value = mock_create_items, mock_delete_items, mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        assert not create_payload
        assert not update_payload
        assert delete_payload.get(FAKE_COURSE_RUN['key']) == past_transmission
        # Sanity check
        mock_get_content_metadata.assert_not_called()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_failed_create_export(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` produces a delete payload of the course data when retrieving catalog
        diffs with content to delete.
        """
        past_transmission = ContentMetadataItemTransmission(
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
        past_transmission.save()
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        mock_create_items = [{'content_key': FAKE_COURSE_RUN['key']}]
        mock_delete_items = []
        mock_matched_items = []
        mock_get_catalog_diff.return_value = mock_create_items, mock_delete_items, mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        assert create_payload.get(FAKE_COURSE_RUN['key']) == past_transmission
        assert not update_payload
        assert not delete_payload

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_truncation_bug_export(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING = {
            'contentId': 'key',
            'title': 'title',
            'description': 'description',
            'imageUrl': 'image',
            'url': 'enrollment_url',
            'language': 'content_language'
        }
        past_transmission_to_update = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission_to_update.save()

        mock_content_metadata_response = OrderedDict()
        mock_content_metadata_response[FAKE_COURSE_RUN['key']] = FAKE_COURSE_RUN
        mock_content_metadata_response[FAKE_COURSE_RUN2['key']] = FAKE_COURSE_RUN2
        mock_api_client.return_value.get_content_metadata.return_value = list(mock_content_metadata_response.values())
        mock_create_items = []
        mock_delete_items = []
        mock_matched_items = [{'content_key': FAKE_COURSE_RUN['key'], 'date_updated': datetime.datetime.now()}]
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export(max_payload_count=1)

        assert update_payload.get(FAKE_COURSE_RUN['key']).channel_metadata.get('contentId') == FAKE_COURSE_RUN['key']
        assert not create_payload
        assert not delete_payload

        mock_api_client.return_value.get_catalog_diff.assert_called_with(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
            [FAKE_COURSE_RUN['key']]
        )

        past_transmission_to_update.content_last_changed = datetime.datetime.now()
        past_transmission_to_update.save()

        past_transmission_to_delete = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN2['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission_to_delete.save()

        mock_delete_items = [{'content_key': FAKE_COURSE_RUN2['key']}]
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items

        create_payload, update_payload, delete_payload = exporter.export(max_payload_count=1)

        assert not update_payload
        assert not create_payload
        assert delete_payload.get(FAKE_COURSE_RUN2['key']) == past_transmission_to_delete
        assert mock_api_client.return_value.get_catalog_diff.call_count == 2
        assert mock_api_client.return_value.get_content_metadata.call_count == 1

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_update_not_needed_export(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` produces a JSON dump of the course data.
        """
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING = {
            'contentId': 'key',
            'title': 'title',
            'description': 'description',
            'imageUrl': 'image',
            'url': 'enrollment_url',
            'language': 'content_language'
        }
        past_transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_id=FAKE_COURSE_RUN['key'],
            channel_metadata={},
            content_last_changed=datetime.datetime.now() - datetime.timedelta(hours=1),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
        )
        past_transmission.save()

        mock_content_metadata_response = OrderedDict()
        mock_content_metadata_response[FAKE_COURSE_RUN['key']] = FAKE_COURSE_RUN
        mock_api_client.return_value.get_content_metadata.return_value = list(mock_content_metadata_response.values())
        mock_create_items = []
        mock_delete_items = []
        mock_matched_items = [{'content_key': FAKE_COURSE_RUN['key'], 'date_updated': datetime.datetime.now()}]
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert update_payload.get(FAKE_COURSE_RUN['key']).channel_metadata.get('contentId') == FAKE_COURSE_RUN['key']
        assert not create_payload
        assert not delete_payload

        mock_api_client.return_value.get_catalog_diff.assert_called_with(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
            [FAKE_COURSE_RUN['key']]
        )

        past_transmission.content_last_changed = datetime.datetime.now()
        past_transmission.save()

        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not create_payload
        assert not delete_payload
        assert mock_api_client.return_value.get_catalog_diff.call_count == 2
        assert mock_api_client.return_value.get_content_metadata.call_count == 1

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_content_exporter_bad_data_transform_mapping(self, mock_api_client):
        """
        ``ContentMetadataExporter``'s ``export`` raises an exception when DATA_TRANSFORM_MAPPING is invalid.
        """
        content_id = 'course:DemoX'

        mock_api_client.return_value.get_content_metadata.return_value = get_fake_content_metadata()
        mock_create_items = [{'content_key': content_id}]
        mock_delete_items = {}
        mock_matched_items = []
        mock_api_client.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        ContentMetadataExporter.DATA_TRANSFORM_MAPPING['fake-key'] = 'fake-value'
        exporter = ContentMetadataExporter('fake-user', self.config)
        with LogCapture(level=logging.ERROR) as log_capture:
            exporter.export()
            assert 'Failed to transform content metadata item field' in log_capture.records[0].getMessage()
            assert self.enterprise_customer_catalog.enterprise_customer.name in log_capture.records[0].getMessage()

    @mock.patch('integrated_channels.integrated_channel.exporters.content_metadata.EnterpriseCatalogApiClient')
    def test_export_fetches_content_only_when_update_needed(self, mock_ent_catalog_api):
        """
        Test that when a ContentMetadataItemTransmission exists with a `catalog_last_changed` field that comes after the
        last modified time of content's associated catalog, we don't fetch the catalog's metadata.
        """
        # Generate a past transmission item that will indicate no updated needed
        past_content_transmission = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2021-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid
        )
        mock_ent_catalog_api.return_value.get_content_metadata.return_value = get_fake_content_metadata()
        mock_create_items = []
        mock_delete_items = {}
        mock_matched_items = [
            {'content_key': past_content_transmission.content_id, 'date_updated': '2021-07-16T15:11:10.521611Z'}
        ]
        mock_ent_catalog_api.return_value.get_catalog_diff.return_value = mock_create_items, mock_delete_items, \
            mock_matched_items
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not create_payload
        assert not update_payload
        assert not delete_payload

        # We should make a call for the enterprise catalog, but no call for the metadata because no update needed
        assert mock_ent_catalog_api.return_value.get_content_metadata.call_count == 0
        assert mock_ent_catalog_api.return_value.get_catalog_diff.call_count == 1

    def test__check_matched_content_updated_at_incomplete_transmission(self):
        """
        Test the __check_matched_content_updated_at function when the transmission is incomplete.
        """
        past_transmission_updated_at_after_mock = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        past_transmission_updated_at_before_mock = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2020-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        past_transmission_updated_at_marked_for = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            marked_for='update',
        )
        mock_matched_items = [
            {'content_key': past_transmission_updated_at_after_mock.content_id,
                'date_updated': '2021-07-16T15:11:10.521611Z'},
            {'content_key': past_transmission_updated_at_before_mock.content_id,
                'date_updated': '2021-07-16T15:11:10.521611Z'},
            {'content_key': past_transmission_updated_at_marked_for.content_id,
                'date_updated': '2021-07-16T15:11:10.521611Z'}
        ]
        exporter = ContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        matched_records = exporter._check_matched_content_updated_at(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
            mock_matched_items,
            False
        )
        assert len(matched_records) == 2

    def test__get_catalog_content_keys_with_deletes(self):
        """
        Test the _get_catalog_content_keys function when the transmission has successful deletes.
        """
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2020-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            remote_deleted_at=datetime.datetime.utcnow(),
            api_response_status_code=200,
        )
        exporter = ContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        matched_records = exporter._get_catalog_content_keys(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
        )
        assert len(matched_records) == 2

    def test__get_catalog_content_keys_failed_deletes(self):
        """
        Test the _get_catalog_content_keys function when the transmission has failed deletes.
        """
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2020-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            remote_deleted_at=datetime.datetime.utcnow(),
            api_response_status_code=500,
        )
        exporter = ContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        matched_records = exporter._get_catalog_content_keys(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
        )
        assert len(matched_records) == 3

    def test__get_catalog_content_keys_failed_creates(self):
        """
        Test the _get_catalog_content_keys function when the transmission has failed deletes.
        """
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2020-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=500,
        )
        exporter = ContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        matched_records = exporter._get_catalog_content_keys(
            self.config.enterprise_customer.enterprise_customer_catalogs.first(),
        )
        assert len(matched_records) == 2

    def test_get_customer_orphaned_content(self):
        """
        Test the get_customer_orphaned_content function.
        """
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            remote_created_at=datetime.datetime.utcnow(),
        )
        orphaned_content = factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            content_id='fake-content-id',
            transmission=transmission_audit,
        )

        exporter = ContentMetadataExporter('fake-user', self.config)

        # pylint: disable=protected-access
        retrieved_orphaned_content = exporter._get_customer_config_orphaned_content(
            max_set_count=1,
        )
        assert len(retrieved_orphaned_content) == 1
        assert retrieved_orphaned_content[0].content_id == orphaned_content.content_id

    def test_get_customer_orphaned_content_under_different_channel(self):
        """
        Test the _get_customer_config_orphaned_content function with records under a separate channel.
        """
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code='foobar',
            remote_created_at=datetime.datetime.utcnow(),
        )
        factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code='foobar',
            plugin_configuration_id=self.config.id,
            content_id='fake-content-id-1',
            transmission=transmission_audit,
        )
        exporter = ContentMetadataExporter('fake-user', self.config)

        # pylint: disable=protected-access
        retrieved_orphaned_content = exporter._get_customer_config_orphaned_content(
            max_set_count=1,
        )
        assert len(retrieved_orphaned_content) == 0

    @override_settings(ALLOW_ORPHANED_CONTENT_REMOVAL=True)
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_fetches_orphaned_content(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` fetches orphaned content to delete.
        """
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            remote_created_at=datetime.datetime.utcnow(),
        )
        orphaned_content = factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            content_id='fake-content-id',
            transmission=transmission_audit,
        )

        mock_exec_ed_content = get_fake_content_metadata()
        mock_get_content_metadata.return_value = mock_exec_ed_content
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()

        exporter = ContentMetadataExporter('fake-user', self.config)
        _, __, delete_payload = exporter.export()

        assert delete_payload == {orphaned_content.content_id: transmission_audit}

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_exporter_skips_orphaned_content_when_at_max_size(self, mock_get_catalog_diff, mock_get_content_metadata):
        """
        ``ContentMetadataExporter``'s ``export`` skips orphaned content when at max size.
        """
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            remote_created_at=datetime.datetime.utcnow(),
        )
        factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            content_id='fake-content-id',
            transmission=transmission_audit,
        )

        mock_exec_ed_content = get_fake_content_metadata()
        mock_get_content_metadata.return_value = mock_exec_ed_content
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()

        exporter = ContentMetadataExporter('fake-user', self.config)
        _, __, delete_payload = exporter.export(max_payload_count=1)

        assert len(delete_payload) == 0
