"""
Tests for the IntegratedChannelAPIRequest admin module in `edx-enterprise`.
"""

from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from integrated_channels.integrated_channel.admin import IntegratedChannelAPIRequestLogAdmin
from integrated_channels.integrated_channel.models import IntegratedChannelAPIRequestLogs
from test_utils import factories


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
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
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
        Test that the get_queryset method optimizes query by using select_related and only selecting specified fields.
        """
        request = None  # or mock a request object if needed
        
        with CaptureQueriesContext(connection) as queries:
            queryset = self.admin.get_queryset(request)

            list(queryset)

        self.assertEqual(len(queries), 1)

        query = queries[0]['sql']
        self.assertIn('integrated_channel_integratedchannelapirequestlogs', query)
        self.assertIn('enterprise_enterprisecustomer', query)

        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."id"', query)
        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."endpoint"', query)
        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."enterprise_customer_id"', query)
        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."time_taken"', query)
        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."status_code"', query)
        self.assertIn('"enterprise_enterprisecustomer"."name"', query)
        self.assertIn('"enterprise_enterprisecustomer"."uuid"', query)
        self.assertIn('"integrated_channel_integratedchannelapirequestlogs"."enterprise_customer_configuration_id"', query)

        self.assertNotIn('payload', query)
        self.assertNotIn('response_body', query)

        log_entry = queryset.get(id=self.log_entry.id)
        self.assertEqual(log_entry.endpoint, "http://test.com")
        self.assertEqual(log_entry.enterprise_customer.name, "Test Enterprise")
        
        with self.assertRaises(AttributeError):
            _ = log_entry.payload
