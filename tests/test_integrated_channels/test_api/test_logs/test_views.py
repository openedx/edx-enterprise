"""
Tests for the `integrated_channels` content and learner sync api.
"""
import datetime
import math
from logging import getLogger
from unittest import mock
from uuid import uuid4

import ddt

from django.urls import reverse

from enterprise.constants import HTTP_STATUS_STRINGS
from enterprise_learner_portal.utils import CourseRunProgressStatuses
from integrated_channels.api.v1.logs.views import ReportingSyncStatusPagination
from test_utils import TEST_PASSWORD, APITest, factories

LOGGER = getLogger(__name__)
TEST_CONTENT_ID = 'DemoX'


@ddt.ddt
class ContentSyncStatusViewSetTests(APITest):
    """
    Tests for ContentSyncStatusViewSet REST endpoints
    """

    def setUp(self):
        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        self.content_metadata_item = factories.ContentMetadataItemTransmissionFactory(
            content_id=TEST_CONTENT_ID,
            content_title='A',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=None,
        )

        super().setUp()

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        if self.content_metadata_item:
            self.content_metadata_item.delete()
        if self.enterprise_customer_catalog:
            self.enterprise_customer_catalog.delete()
        super().tearDown()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_view_ignores_random_query_params(self):
        """
        Test that a random query param is not interpretted as a filter
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + '?ahsdfhasdfhahsdfhasd=ayylmao'

        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert 1 == response_json.get('count')
        # check that it didn't consider the query param a filter
        assert self.content_metadata_item.content_title == response_json['results'][0]['content_title']

    def test_view_filters_and_sorts_simultaneously(self):
        """
        Test that the view properly handles a sort_by filter and a field filter simultaneously
        """
        # Same content ID as self.content_metadata_item but a different content_title
        factories.ContentMetadataItemTransmissionFactory(
            content_id='DemoX_X',
            content_title='B',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=None,
        )

        # Different content ID
        factories.ContentMetadataItemTransmissionFactory(
            content_id='Something Else',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=None,
        )
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + '?sort_by=content_title&content_id=DemoX'

        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert 2 == response_json.get('count')
        assert response_json.get('results')[0].get('content_title') == 'A'
        assert response_json.get('results')[1].get('content_title') == 'B'

        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + '?sort_by=-content_title&content_id=DemoX'

        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert 2 == response_json.get('count')
        assert response_json.get('results')[1].get('content_title') == 'A'
        assert response_json.get('results')[0].get('content_title') == 'B'

    def test_view_includes_number_of_total_pages(self):
        """
        Test that the ContentSyncStatusViewSet surfaces total number of pages of data exist for a given request
        """
        num_records = 50
        for x in range(num_records):
            factories.ContentMetadataItemTransmissionFactory(
                content_id=f'DemoX {x}',
                enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
                integrated_channel_code='GENERIC',
                plugin_configuration_id=1,
                remote_created_at=datetime.datetime.utcnow(),
                api_response_status_code=None,
            )

        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        # Assert that the number of total pages is equal to the number of records (num_records + the record
        # created in the setup) divided by the page size
        assert response_json.get('pages_count') == \
            math.ceil((num_records + 1) / ReportingSyncStatusPagination.page_size)

    def test_view_supports_field_filters(self):
        """
        Test that the ContentSyncStatusViewSet supports field specific filtering
        """
        content_id_filter = 'Find this one'
        factories.ContentMetadataItemTransmissionFactory(
            content_id=content_id_filter,
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=None,
        )

        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + f'?content_id={content_id_filter}'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert len(response_json.get('results')) == 1
        assert response_json.get('results')[0].get('content_id') == 'Find this one'

    def test_view_default_sorts_by_status_code(self):
        """
        Test that the ContentSyncStatusViewSet defaults to sorting by status code if a status code
        query param is not specified
        """
        factories.ContentMetadataItemTransmissionFactory(
            content_id='Demo test_view_default_sorts_by_status_code 1',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=400,
        )

        factories.ContentMetadataItemTransmissionFactory(
            content_id='Demo test_view_default_sorts_by_status_code 2',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=200,
        )

        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json.get('results')[0].get('sync_status') == 'error'
        assert response_json.get('results')[1].get('sync_status') == 'okay'

    def test_view_validates_sort_by_params(self):
        """
        Test that the ContentSyncStatusViewSet validates the `sort_by` query param
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + '?sort_by=INVALID_PARAM'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json == {'detail': 'Invalid sort_by filter.'}

    @ddt.data(
        # Base case- no datetimes, `A` comes before the test content metadata
        (
            None,
            None,
            None,
            None,
            None,
            None,
            'A',
            TEST_CONTENT_ID,
            '',
        ),
        # Ordering (`-` and lack thereof) tests
        (
            datetime.datetime.utcnow(),
            None,
            None,
            datetime.datetime.utcnow() - datetime.timedelta(days=10),
            None,
            None,
            'A',
            TEST_CONTENT_ID,
            '-',
        ),
        (
            datetime.datetime.utcnow(),
            None,
            None,
            datetime.datetime.utcnow() - datetime.timedelta(days=10),
            None,
            None,
            TEST_CONTENT_ID,
            'A',
            '',
        ),
        # tests existing values are ordered higher compared to null values
        (
            datetime.datetime.utcnow(),
            None,
            None,
            None,
            None,
            None,
            'A',
            TEST_CONTENT_ID,
            '-',
        ),
        # tests filtering one remote timestamp with a different one (created at )
        (
            datetime.datetime.utcnow() - datetime.timedelta(days=1),
            datetime.datetime.utcnow() - datetime.timedelta(days=15),
            None,
            datetime.datetime.utcnow() - datetime.timedelta(days=10),
            datetime.datetime.utcnow(),
            None,
            TEST_CONTENT_ID,
            'A',
            '-',
        ),
    )
    @ddt.unpack
    def test_view_properly_sorts_sync_dates(
        self,
        remote_updated_at,
        remote_created_at,
        remote_deleted_at,
        remote_created_at_2,
        remote_updated_at_2,
        remote_deleted_at_2,
        first_result,
        second_result,
        order
    ):
        """
        Test that the ContentSyncStatusViewSet properly filters by remote timestamps under the `sync_status` field
        """
        factories.ContentMetadataItemTransmissionFactory(
            content_id='A',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=remote_created_at,
            remote_updated_at=remote_updated_at,
            remote_deleted_at=remote_deleted_at,
            api_response_status_code=200,
        )

        self.content_metadata_item.remote_created_at = remote_created_at_2
        self.content_metadata_item.remote_updated_at = remote_updated_at_2
        self.content_metadata_item.remote_deleted_at = remote_deleted_at_2
        self.content_metadata_item.save()

        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + f'?sort_by={order}sync_last_attempted_at'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json.get('results')[0].get('content_id') == first_result
        assert response_json.get('results')[1].get('content_id') == second_result

    def test_view_allows_for_sort_by_filters(self):
        """
        Test that the ContentSyncStatusViewSet supports custom queryset ordering by specifying a `sort_by` query param
        """
        factories.ContentMetadataItemTransmissionFactory(
            content_id='B',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=400,
        )

        factories.ContentMetadataItemTransmissionFactory(
            content_id='A',
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
            integrated_channel_code='GENERIC',
            plugin_configuration_id=1,
            remote_created_at=datetime.datetime.utcnow(),
            api_response_status_code=200,
        )

        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        ) + '?sort_by=content_id'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json.get('results')[0].get('content_id') == 'A'
        assert response_json.get('results')[1].get('content_id') == 'B'

    def test_get(self):
        """
        tests a regular get with expected data
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.content_metadata_item.content_title == response_json['results'][0]['content_title']
        assert self.content_metadata_item.content_id == response_json['results'][0]['content_id']
        assert 'pending' == response_json['results'][0]['sync_status']
        assert 'sync_last_attempted_at' in response_json['results'][0].keys()

    def test_get_with_bad_channel_code(self):
        """
        tests that an invalid channel_code results in a 400
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = self.enterprise_customer_catalog.enterprise_customer.uuid
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'BROKEN',
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        assert response.status_code == 400

    @ddt.data('CANVAS', 'BLACKBOARD', 'CSOD', 'DEGREED', 'DEGREED2', 'MOODLE', 'SAP')
    def test_gets_of_all_channels(self, app_label):
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': app_label,
                'plugin_configuration_id': 1
            }
        )
        response = self.client.get(url)
        assert response.status_code == 200

    @ddt.data(
        (400, HTTP_STATUS_STRINGS[400]),
        (401, HTTP_STATUS_STRINGS[401]),
        (403, HTTP_STATUS_STRINGS[403]),
        (404, HTTP_STATUS_STRINGS[404]),
        (408, HTTP_STATUS_STRINGS[408]),
        (429, HTTP_STATUS_STRINGS[429]),
        (500, HTTP_STATUS_STRINGS[500]),
        (503, HTTP_STATUS_STRINGS[503]),
        (12345, None)
    )
    @ddt.unpack
    def test_get_friendly_status_message(self, status, expected_status_message):
        """
        tests learner data transmission audit API serializer sync status value based on transmission audit status
        """
        self.setup_admin_user(True)
        expected_enterprise_uuid = str(self.enterprise_customer_catalog.enterprise_customer.uuid)
        url = reverse(
            'api:v1:logs:content_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': expected_enterprise_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': 1
            }
        )
        self.content_metadata_item.api_response_status_code = status
        self.content_metadata_item.save()
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert response_json['results'][0]['friendly_status_message'] == expected_status_message


@ddt.ddt
class LearnerSyncStatusViewSetTests(APITest):
    """
    Tests for LearnerSyncStatusViewSet REST endpoints
    """

    def setUp(self):

        with mock.patch('enterprise.signals.EnterpriseCatalogApiClient'):
            self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        self.generic_audit = factories.GenericLearnerDataTransmissionAuditFactory(
            course_id='DemoXYZ',
            content_title='A',
            user_email='zfoobar@ayylmao.com',
            status=200,
        )
        self.sap_audit = factories.SapSuccessFactorsLearnerDataTransmissionAuditFactory(
            content_title='DemoX',
            enterprise_customer_uuid=self.enterprise_customer_catalog.enterprise_customer.uuid,
            plugin_configuration_id=1,
            status=200,
            user_email='totallynormalemail@example.com',
            progress_status=CourseRunProgressStatuses.IN_PROGRESS,
        )
        super().setUp()

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        if self.generic_audit:
            self.generic_audit.delete()
        if self.sap_audit:
            self.sap_audit.delete()
        super().tearDown()

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def test_get_excludes_unneeded_fields(self):
        """
        tests that a get request will not return unneeded fields
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)

        # check that it excludes expected data
        assert "course_completed" not in response_json['results'][0].keys()
        assert "instructor_name" not in response_json['results'][0].keys()
        assert "course_id" not in response_json['results'][0].keys()

    def test_view_ignores_random_query_params(self):
        """
        Test that a random query param is not interpretted as a filter
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + '?ahsdfhasdfhahsdfhasd=ayylmao'

        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert 1 == response_json.get('count')
        # check that it didn't consider the query param a filter
        assert self.generic_audit.content_title == response_json['results'][0]['content_title']

    def test_view_filters_and_sorts_simultaneously(self):
        """
        Test that the LearnerSyncStatusViewSet properly handles a sort_by filter and a field filter simultaneously
        """
        # Same course ID as self.generic_audit but a different, sortable content_title
        factories.GenericLearnerDataTransmissionAuditFactory(
            course_id=self.generic_audit.course_id,
            content_title='B',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=200,
        )

        # Different course ID, should not get picked up because of feild filter
        factories.GenericLearnerDataTransmissionAuditFactory(
            course_id='Something Else',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=200,
        )
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + f'?sort_by=content_title&course_id={self.generic_audit.course_id}'

        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert 2 == response_json.get('count')
        assert response_json.get('results')[0].get('content_title') == 'A'
        assert response_json.get('results')[1].get('content_title') == 'B'

        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + f'?sort_by=-content_title&course_id={self.generic_audit.course_id}'

        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert 2 == response_json.get('count')
        assert response_json.get('results')[1].get('content_title') == 'A'
        assert response_json.get('results')[0].get('content_title') == 'B'

    def test_view_includes_number_of_total_pages(self):
        """
        Test that the LearnerSyncStatusViewSet surfaces total number of pages of data exist for a given request
        """
        num_records = 50
        for x in range(num_records):
            factories.GenericLearnerDataTransmissionAuditFactory(
                content_title=f'Demo{x}',
                enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
                plugin_configuration_id=self.generic_audit.plugin_configuration_id,
                status=200,
            )

        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )

        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert response_json.get('pages_count') == math.ceil(
            (num_records + 1) / ReportingSyncStatusPagination.page_size
        )

    def test_view_supports_sync_status_filters(self):
        """
        Test that the LearnerSyncStatusViewSet supports sync status datetime filtering
        """
        now = datetime.datetime.utcnow()
        self.generic_audit.created = now - datetime.timedelta(days=1)
        self.generic_audit.save()
        comes_first = factories.GenericLearnerDataTransmissionAuditFactory(
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            modified=now,
        )
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + '?sort_by=-sync_last_attempted_at'
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert response_json.get('results')[0].get('content_title') == comes_first.content_title
        assert response_json.get('results')[1].get('content_title') == self.generic_audit.content_title

    def test_view_supports_field_filters(self):
        """
        Test that the LearnerSyncStatusViewSet supports field specific filtering
        """
        user_email_filter = 'Find this one'
        factories.GenericLearnerDataTransmissionAuditFactory(
            user_email=user_email_filter,
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=200,
        )
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + '?sort_by=user_email'
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert user_email_filter == response_json.get('results')[0].get('user_email')

    def test_view_default_sorts_by_status(self):
        """
        Test that the LearnerSyncStatusViewSet defaults to sorting by status code if a status code
        query param is not specified
        """
        factories.GenericLearnerDataTransmissionAuditFactory(
            user_email='200@test.com',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=201,
        )
        factories.GenericLearnerDataTransmissionAuditFactory(
            user_email='400@test.com',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=500,
        )
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json.get('results')[0].get('user_email') == '400@test.com'
        assert response_json.get('results')[1].get('user_email') == '200@test.com'

    def test_view_validates_sort_by_params(self):
        """
        Test that the LearnerSyncStatusViewSet validates the `sort_by` query param
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + '?sort_by=INVALID_PARAM'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json == {'detail': 'Invalid sort_by filter.'}

    def test_view_allows_for_sort_by_filters(self):
        """
        Test that the LearnerSyncStatusViewSet supports custom queryset ordering by specifying a `sort_by` query param
        """
        factories.GenericLearnerDataTransmissionAuditFactory(
            user_email='200@test.com',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=200,
        )
        factories.GenericLearnerDataTransmissionAuditFactory(
            user_email='400@test.com',
            enterprise_customer_uuid=self.generic_audit.enterprise_customer_uuid,
            plugin_configuration_id=self.generic_audit.plugin_configuration_id,
            status=400,
        )
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        ) + '?sort_by=user_email'
        response = self.client.get(url)
        response_json = self.load_json(response.content)

        assert response_json.get('results')[0].get('user_email') == '200@test.com'
        assert response_json.get('results')[1].get('user_email') == '400@test.com'

    def test_get(self):
        """
        tests a regular get with expected data
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )

        # user_email, content_title, progress_status, sync_status, sync_last_attempted_at, friendly_status_message
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.generic_audit.content_title == response_json['results'][0]['content_title']

        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.sap_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'SAP',
                'plugin_configuration_id': self.sap_audit.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        LOGGER.info(response.content)
        response_json = self.load_json(response.content)
        # check for pagination, ensure correct count
        assert 1 == response_json.get('count')
        # check that it includes expected data
        assert self.sap_audit.user_email == response_json['results'][0]['user_email']
        assert self.sap_audit.progress_status == response_json['results'][0]['progress_status']
        assert 'okay' == response_json['results'][0]['sync_status']
        assert 'sync_last_attempted_at' in response_json['results'][0].keys()
        assert response_json['results'][0]['friendly_status_message'] is None

    def test_gets_of_all_channels(self):
        app_labels = ['CANVAS', 'BLACKBOARD', 'CORNERSTONE', 'DEGREED', 'DEGREED2', 'MOODLE', 'SAP']
        self.setup_admin_user(True)
        for label in app_labels:
            url = reverse(
                'api:v1:logs:learner_sync_status_logs',
                kwargs={
                    'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                    'integrated_channel_code': label,
                    'plugin_configuration_id': self.generic_audit.plugin_configuration_id
                }
            )
            response = self.client.get(url)
            assert response.status_code == 200

    @ddt.data((None, 'pending'), ('400', 'error'), ('200', 'okay'))
    @ddt.unpack
    def test_get_sync_statuses(self, audit_status, expected_sync_status):
        """
        tests learner data transmission audit API serializer sync status value based on transmission audit status
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )
        self.generic_audit.status = audit_status
        self.generic_audit.save()
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert response_json['results'][0]['sync_status'] == expected_sync_status

    @ddt.data(
        (400, HTTP_STATUS_STRINGS[400]),
        (401, HTTP_STATUS_STRINGS[401]),
        (403, HTTP_STATUS_STRINGS[403]),
        (404, HTTP_STATUS_STRINGS[404]),
        (408, HTTP_STATUS_STRINGS[408]),
        (429, HTTP_STATUS_STRINGS[429]),
        (500, HTTP_STATUS_STRINGS[500]),
        (503, HTTP_STATUS_STRINGS[503]),
        (12345, None)
    )
    @ddt.unpack
    def test_get_friendly_status_message(self, audit_status, expected_status_message):
        """
        tests learner data transmission audit API serializer sync status value based on transmission audit status
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'GENERIC',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )
        self.generic_audit.status = audit_status
        self.generic_audit.save()
        response = self.client.get(url)
        response_json = self.load_json(response.content)
        assert response_json['results'][0]['friendly_status_message'] == expected_status_message

    def test_get_with_bad_channel_code(self):
        """
        tests that an invalid channel_code results in a 400
        """
        self.setup_admin_user(True)
        url = reverse(
            'api:v1:logs:learner_sync_status_logs',
            kwargs={
                'enterprise_customer_uuid': self.generic_audit.enterprise_customer_uuid,
                'integrated_channel_code': 'BROKEN',
                'plugin_configuration_id': self.generic_audit.plugin_configuration_id
            }
        )
        response = self.client.get(url)
        assert response.status_code == 400
        response_json = self.load_json(response.content)
        assert 'Invalid channel code.' == response_json['detail']


@ddt.ddt
class IntegratedChannelsBaseViewSetTests(APITest):
    """
    Tests for configs list endpoint
    """

    def setup_admin_user(self, is_staff=True):
        """
        Creates an admin user and logs them in
        """
        client_username = 'client_username'
        self.client.logout()
        self.create_user(username=client_username, password=TEST_PASSWORD, is_staff=is_staff)
        self.client.login(username=client_username, password=TEST_PASSWORD)

    def setUp(self):
        customer_uuid = uuid4()
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=customer_uuid)

        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.degreed_config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            last_sync_attempted_at=datetime.datetime.fromtimestamp(1644883200),
            last_content_sync_attempted_at=datetime.datetime.fromtimestamp(1486855998),
            last_learner_sync_attempted_at=datetime.datetime.fromtimestamp(1644883200),
            last_sync_errored_at=datetime.datetime.fromtimestamp(1386855998),
            last_content_sync_errored_at=datetime.datetime.fromtimestamp(1386855998),
            last_learner_sync_errored_at=None,
        )
        self.degreed_content_transmission_1 = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer,
            content_title='course-v1:edX+DemoX+DemoCourse3',
            integrated_channel_code=self.degreed_config.channel_code(),
            plugin_configuration_id=self.degreed_config.id,
            api_response_status_code='200',
            channel_metadata={},
            remote_created_at=datetime.datetime.fromtimestamp(1486855998),
            remote_updated_at=datetime.datetime.fromtimestamp(1586855998),
            remote_deleted_at=datetime.datetime.fromtimestamp(1486856000),
        )
        self.degreed_content_transmission_2 = factories.ContentMetadataItemTransmissionFactory(
            enterprise_customer=self.enterprise_customer,
            content_title='course-v1:edX+DemoX+DemoCourse4',
            integrated_channel_code=self.degreed_config.channel_code(),
            plugin_configuration_id=self.degreed_config.id,
            api_response_status_code='400',
            channel_metadata={},
            remote_created_at=datetime.datetime.fromtimestamp(1386855998),
        )
        self.degreed_learner_audit_1 = factories.DegreedLearnerDataTransmissionAuditFactory(
            enterprise_customer_uuid=customer_uuid,
            course_id='course-v1:edX+DemoX+DemoCourse5',
            plugin_configuration_id=self.degreed_config.id,
            status='200',
            degreed_completed_timestamp='2022-02-15',
            completed_timestamp=datetime.datetime.fromtimestamp(1644883200),
        )

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        super().tearDown()

    def test_get_list(self):
        self.setup_admin_user(True)
        url = reverse('api:v1:configs')
        full_url = url + "?enterprise_customer=" + str(self.enterprise_customer.uuid)
        response = self.client.get(full_url)
        response_json = self.load_json(response.content)

        assert response_json[0]['last_sync_attempted_at'] == '2022-02-15T00:00:00Z'
        assert response_json[0]['last_content_sync_attempted_at'] == '2017-02-11T23:33:18Z'
        assert response_json[0]['last_learner_sync_attempted_at'] == '2022-02-15T00:00:00Z'
        assert response_json[0]['last_sync_errored_at'] == '2013-12-12T13:46:38Z'
        assert response_json[0]['last_content_sync_errored_at'] == '2013-12-12T13:46:38Z'
        assert response_json[0]['last_learner_sync_errored_at'] is None
