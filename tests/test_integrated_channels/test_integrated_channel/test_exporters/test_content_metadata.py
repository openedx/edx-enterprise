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
from django.utils import timezone

from enterprise.constants import EXEC_ED_COURSE_TYPE
from enterprise.utils import get_content_metadata_item_id
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from integrated_channels.sap_success_factors.exporters.content_metadata import SapSuccessFactorsContentMetadataExporter
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
        self.content_id = "NYIF+BOPC.4x"
        self.mock_metadata = {
            "aggregation_key": "course:NYIF+BOPC.4x",
            "content_type": "course",
            "full_description": "ayylmao",
            "key": self.content_id,
            "title": "Brokerage Operations Professional Certificate Examination",
            "course_runs": [
                {
                    "key": "course-v1:NYIF+BOPC.4x+3T2017",
                    "uuid": "69b38e2f-e041-4634-b537-fc8d8e12c87e",
                    "title": "Brokerage Operations Professional Certificate Examination",
                    "short_description": "ayylmao",
                    "availability": "Archived",
                    "pacing_type": "self_paced",
                    "seats": [
                        {
                            "type": "professional",
                            "price": "500.00",
                            "currency": "USD",
                            "upgrade_deadline": None,
                            "upgrade_deadline_override": None,
                            "credit_provider": None,
                            "credit_hours": None,
                            "sku": "0C1BF31",
                            "bulk_sku": "668527E"
                        }
                    ],
                    "start": "2017-09-07T00:00:00Z",
                    # A none value here will cause the sanitization to remove the schedule blob
                    "end": None,
                }
            ],
            "uuid": "bbbf059e-b9fb-4ad7-a53e-4c6f85f47f4e",
            "end_date": "2019-09-07T00:00:00Z",
            "course_ends": "Future",
            "entitlements": [],
            "modified": "2023-07-10T04:29:38.934204Z",
            "additional_information": None,
            "course_run_keys": [
                "course-v1:NYIF+BOPC.4x+3T2017",
                "course-v1:NYIF+BOPC.4x+1T2017"
            ],
            "enrollment_url": "https://foobar.com"
        }
        self.channel_metadata = {
            "courseID": "NYIF+BOPC.4x",
            "providerID": "EDX",
            # This status should be transformed to `INACTIVE` by the exporter
            "status": "ACTIVE",
            "title": [{
                "locale": "English",
                "value": "Brokerage Operations Professional Certificate Examination"
            }],
            "content": [
                {
                    "providerID": "EDX",
                    "contentTitle": "Brokerage Operations Professional Certificate Examination",
                    "contentID": "NYIF+BOPC.4x",
                    "launchType": 3,
                    "mobileEnabled": True,
                }
            ],
            "schedule": [
                {
                    "startDate": "",
                    "endDate": "",
                    "active": False,
                    "duration": "0 days"
                }
            ],
            "price": [
                {
                    "currency": "USD",
                    "value": 0.0
                }
            ]
        }
        super().setUp()

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_exporter_transforms_metadata_of_items_to_be_deleted(
        self,
        mock_get_catalog_diff,
        mock_get_content_metadata,
    ):
        """
        Test that the exporter properly transforms the metadata of items that are to be deleted.
        """
        sap_config = factories.SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Existing audit metadata, needs to be updated/transformed.
        # According to the SAP channel, upon deletion we need to set each content metadata blob's status to `INACTIVE`.
        # Additionally, according to the mocked catalog metadata, the transformed mappings of the record need ot be
        # updated. We will assert that both of these transformations are applied by the exporter.

        content_id_to_skip = "CTIF+BOPC.4x"

        # Create the transmission audit with the out of date channel metadata
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            content_id=self.content_id,
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=sap_config.id,
            integrated_channel_code=sap_config.channel_code(),
            channel_metadata=self.channel_metadata,
            remote_created_at=datetime.datetime.utcnow(),
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            remote_errored_at=None,
        )
        # explicitly set modified timestamp to a value older than remote_errored_at
        self.config.enterprise_customer.modified = timezone.now() - timezone.timedelta(hours=40)
        transmission_audit_to_skip = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_to_skip,
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=sap_config.id,
            integrated_channel_code=sap_config.channel_code(),
            channel_metadata=self.channel_metadata,
            remote_created_at=datetime.datetime.utcnow(),
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            # failed within last 24hrs
            remote_errored_at=timezone.now() - timezone.timedelta(hours=23),
        )

        # Mock the catalog service to return the metadata of the content to be deleted
        mock_get_content_metadata.return_value = [self.mock_metadata]
        # Mock the catalog service to return the content to be deleted in the delete payload
        mock_get_catalog_diff.return_value = (
            [], [{'content_key': transmission_audit.content_id}], [])
        exporter = SapSuccessFactorsContentMetadataExporter(
            'fake-user', sap_config)
        _, _, delete_payload = exporter.export()
        assert delete_payload[transmission_audit.content_id].channel_metadata.get(
            'schedule') == []
        assert delete_payload[transmission_audit.content_id].channel_metadata.get(
            'status') == 'INACTIVE'

        # if transmission was attempted in last 24hrs, it shouldn't be reattempted
        mock_get_catalog_diff.return_value = (
            [], [{'content_key': transmission_audit_to_skip.content_id}], [])
        exporter = SapSuccessFactorsContentMetadataExporter(
            'fake-user', sap_config)
        _, _, delete_payload = exporter.export()
        assert not delete_payload

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_exporter_force_transmit_works(
        self,
        mock_get_catalog_diff,
        mock_get_content_metadata,
    ):
        """
        Test that the exporter properly exports failed transmission if customer configs are changed
        within 24hrs after it was failed. It's decided based on enterprise_customer.modified
        and remote_created_at timestamp
        """
        sap_config = factories.SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        content_id_to_not_skip = "MTIF+BOPC.4x"

        # explicitly set modified timestamp to a value greater than remote_errored_at
        # to make sure that we're force transmitting failed transmissions if customer
        # configs are changed before 24hrs are passed
        self.config.enterprise_customer.modified = timezone.now() - \
            timezone.timedelta(hours=20)
        transmission_audit_to_skip = factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_to_not_skip,
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=sap_config.id,
            integrated_channel_code=sap_config.channel_code(),
            channel_metadata=self.channel_metadata,
            remote_created_at=datetime.datetime.utcnow(),
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            # failed within last 24hrs
            remote_errored_at=timezone.now() - timezone.timedelta(hours=23),
        )

        # Mock the catalog service to return the metadata of the content to be deleted
        mock_get_content_metadata.return_value = [self.mock_metadata]

        # Mock the catalog service to return the content to be deleted in the delete payload
        mock_get_catalog_diff.return_value = (
            [], [{'content_key': transmission_audit_to_skip.content_id}], [])
        exporter = SapSuccessFactorsContentMetadataExporter(
            'fake-user', sap_config)

        # We don't reattempt transmission if transmission it failed in last 24hrs
        # But if within 24hrs, customer configurations are changed then we reattempt to transmit
        # even though 24hrs aren't yet passed

        _, _, delete_payload = exporter.export()
        assert delete_payload == {
            transmission_audit_to_skip.content_id: transmission_audit_to_skip}

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_exporter_get_catalog_diff_works_with_orphaned_content(self, mock_get_catalog_diff):
        """
        Test that the exporter _get_catalog_diff function properly marks orphaned content that is requested to be
        created by another, linked catalog as resolved.
        """
        transmission_audit = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            remote_created_at=datetime.datetime.utcnow(),
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
        )
        orphaned_content = factories.OrphanedContentTransmissionsFactory(
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            content_id=FAKE_COURSE_RUN['key'],
            transmission=transmission_audit,
            resolved=False,
        )
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()

        exporter = ContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        _, __, ___ = exporter._get_catalog_diff(
            enterprise_catalog=self.enterprise_customer_catalog,
            content_keys=FAKE_COURSE_RUN['key'],
            force_retrieve_all_catalogs=False,
            max_item_count=10000000,
        )
        orphaned_content.refresh_from_db()
        assert orphaned_content.resolved

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_exporter_considers_failed_updates_as_existing_content(
        self,
        mock_get_catalog_diff,
        mock_get_content_metadata
    ):
        """
        Test the exporter considers audits that failed to update as existing content.
        """
        self.enterprise_customer_catalog.enterprise_customer.modified = timezone.now() - timezone.timedelta(hours=40)
        test_failed_updated_content = ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            content_last_changed=None,
            api_response_status_code=500,
            # didn't failed within last 24hrs
            remote_errored_at=timezone.now() - timezone.timedelta(hours=25),
        )
        mock_metadata = get_fake_content_metadata()[:1]
        mock_metadata[0]['key'] = test_failed_updated_content.content_id

        mock_get_content_metadata.return_value = mock_metadata

        # Mock out a response from the catalog service indicating that the content needs to be created
        mock_get_catalog_diff.return_value = (
            [{'content_key': test_failed_updated_content.content_id}], [], []
        )
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, _, __ = exporter.export()

        # The exporter is supposed to consider failed updates as existing content, so the content should not be in the
        # create payload, even though the catalog service thinks it should be created.
        assert not create_payload

        # The exporter should include the failed update audit in the payload of content keys passed to the enterprise
        # catalog service diff endpoint.
        assert mock_get_catalog_diff.call_args.args[1] == [test_failed_updated_content.content_id]

        # Mock out a response from the catalog service (correctly) indicating that the content needs to be updated
        mock_get_catalog_diff.return_value = (
            [], [], [{'content_key': test_failed_updated_content.content_id, 'date_updated': datetime.datetime.now()}]
        )
        _, update_payload, __ = exporter.export()

        # The exporter should now properly include the content in the update payload.
        assert update_payload == {test_failed_updated_content.content_id: test_failed_updated_content}

        # shouldn't export if it errored in last 24hrs
        exporter = ContentMetadataExporter('fake-user', self.config)
        content_id_to_skip = "CTIF+BOPC.4x"
        test_failed_updated_content_to_skip = ContentMetadataItemTransmissionFactory(
            content_id=content_id_to_skip,
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog.uuid,
            integrated_channel_code=self.config.channel_code(),
            plugin_configuration_id=self.config.id,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
            content_last_changed=None,
            api_response_status_code=500,
            # failed within last 24hrs
            remote_errored_at=timezone.now() - timezone.timedelta(hours=23),
        )
        mock_get_catalog_diff.return_value = (
            [], [], [{'content_key': test_failed_updated_content_to_skip.content_id,
                      'date_updated': datetime.datetime.now()}]
        )
        _, update_payload, __ = exporter.export()
        assert not update_payload

    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_content_metadata')
    @mock.patch('enterprise.api_client.enterprise_catalog.EnterpriseCatalogApiClient.get_catalog_diff')
    def test_content_exporter_create_export(self, mock_get_catalog_diff, mock_get_content_metadata):
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
        mock_get_content_metadata.return_value = get_fake_content_metadata()
        mock_get_catalog_diff.return_value = get_fake_catalog_diff_create()
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()

        assert not update_payload
        assert not delete_payload

        assert mock_get_content_metadata.get(FAKE_COURSE_RUN['key'])

        for key in create_payload:
            assert key in [FAKE_COURSE['key'], FAKE_COURSE_RUN.get('key'), FAKE_UUIDS[3]]
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
        mock_get_content_metadata.return_value = [FAKE_COURSE_RUN]
        exporter = ContentMetadataExporter('fake-user', self.config)
        create_payload, update_payload, delete_payload = exporter.export()
        assert not create_payload
        assert not update_payload
        assert delete_payload.get(FAKE_COURSE_RUN['key']) == past_transmission

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
            remote_errored_at=None,
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

        mock_api_client.return_value.get_catalog_diff.reset_mock()
        mock_api_client.return_value.get_content_metadata.reset_mock()

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
        # get_catalog_diff is called once per customer catalog
        assert mock_api_client.return_value.get_catalog_diff.call_count == 1
        # get_content_metadata isn't called for the item to delete
        assert mock_api_client.return_value.get_content_metadata.call_count == 0

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
        fake_content_metadata = get_fake_content_metadata()
        content_id = fake_content_metadata[0].get('key')

        mock_api_client.return_value.get_content_metadata.return_value = fake_content_metadata
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
        # Successfully created and updated audit, updated now()
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        # Successfully created and updated audit, updated a while ago
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed='2020-07-16T15:11:10.521611Z',
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            remote_updated_at=datetime.datetime.utcnow(),
        )
        # Failed to create audit, updated now(). No updated_at or deleted_at
        factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.config.enterprise_customer,
            plugin_configuration_id=self.config.id,
            integrated_channel_code=self.config.channel_code(),
            content_last_changed=datetime.datetime.now(),
            enterprise_customer_catalog_uuid=self.config.enterprise_customer.enterprise_customer_catalogs.first().uuid,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=500,
            remote_updated_at=None,
            remote_deleted_at=None,
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
