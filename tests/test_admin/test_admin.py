from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test.utils import CaptureQueriesContext
from integrated_channels.integrated_channel.admin import IntegratedChannelAPIRequestLogAdmin
from integrated_channels.integrated_channel.models import IntegratedChannelAPIRequestLogs, EnterpriseCustomer


class IntegratedChannelAPIRequestLogAdminTest(TestCase):
    """
    Test the admin functionality for the IntegratedChannelAPIRequestLogs model.
    """

    def setUp(self):
        """
        Set up the test environment by creating a test admin instance and sample data.
        """
        self.site = AdminSite()
        self.admin = IntegratedChannelAPIRequestLogAdmin(IntegratedChannelAPIRequestLogs, self.site)
        
        # Create test data
        self.enterprise_customer = EnterpriseCustomer.objects.create(name="Test Enterprise", uuid="test-uuid")
        self.log_entry = IntegratedChannelAPIRequestLogs.objects.create(
            enterprise_customer=self.enterprise_customer,
            enterprise_customer_configuration_id=1,
            endpoint="http://test.com",
            payload="test payload",
            time_taken=1.0,
            status_code=200,
            response_body="test response"
        )

    def test_get_queryset_optimization(self):
        """
        Test that the get_queryset method optimizes the query by using select_related and only selecting specified fields.
        """
        request = None  # or mock a request object if needed
        
        with CaptureQueriesContext(connection) as queries:
            queryset = self.admin.get_queryset(request)
            # Force evaluation of the queryset
            list(queryset)

        # Check that only one query is executed (thanks to select_related)
        self.assertEqual(len(queries), 1)

        # Check that the query includes both the main table and the related table
        query = queries[0]['sql']
        self.assertIn('integrated_channel_api_request_logs', query)
        self.assertIn('enterprise_customer', query)

        # Check that only the specified fields are selected
        self.assertIn('integrated_channel_api_request_logs.id', query)
        self.assertIn('integrated_channel_api_request_logs.endpoint', query)
        self.assertIn('integrated_channel_api_request_logs.enterprise_customer_id', query)
        self.assertIn('integrated_channel_api_request_logs.time_taken', query)
        self.assertIn('integrated_channel_api_request_logs.status_code', query)
        self.assertIn('enterprise_customer.name', query)
        self.assertIn('enterprise_customer.uuid', query)
        self.assertIn('integrated_channel_api_request_logs.enterprise_customer_configuration_id', query)

        # Check that unspecified fields are not selected
        self.assertNotIn('integrated_channel_api_request_logs.payload', query)
        self.assertNotIn('integrated_channel_api_request_logs.response_body', query)

        # Verify that the queryset returns the expected data
        log_entry = queryset.get(id=self.log_entry.id)
        self.assertEqual(log_entry.endpoint, "http://test.com")
        self.assertEqual(log_entry.enterprise_customer.name, "Test Enterprise")
        
        # Verify that accessing an unselected field raises an error
        with self.assertRaises(AttributeError):
            _ = log_entry.payload
