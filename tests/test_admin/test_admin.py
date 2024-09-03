"""
Tests for the IntegratedChannelAPIRequest admin module in `edx-enterprise`.
"""
from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from enterprise.admin import EnterpriseGroupMembershipAdmin
from enterprise.models import EnterpriseGroupMembership
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

        self.enterprise_customer = factories.EnterpriseCustomerFactory(name='Test Enterprise')
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
        request = None

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
        self.assertIn(
            '"integrated_channel_integratedchannelapirequestlogs"."enterprise_customer_configuration_id"', query
        )

        self.assertNotIn('payload', query)
        self.assertNotIn('response_body', query)

        log_entry = queryset.get(id=self.log_entry.id)
        self.assertEqual(log_entry.endpoint, "http://test.com")
        self.assertEqual(log_entry.enterprise_customer.name, "Test Enterprise")

        # Verify that accessing an unselected field causes an additional query
        with CaptureQueriesContext(connection) as queries:
            _ = log_entry.payload

        self.assertEqual(len(queries), 1, "Accessing unselected field should cause exactly one additional query")


class EnterpriseGroupMembershipAdminTest(TestCase):
    """
    Test the admin functionality for the EnterpriseGroupMembership model.
    """

    def setUp(self):
        """
        Set up the test environment by creating a test admin instance and sample data.
        """
        self.site = AdminSite()
        self.admin = EnterpriseGroupMembershipAdmin(EnterpriseGroupMembership, self.site)

        self.egm_1 = factories.EnterpriseGroupMembershipFactory()
        self.egm_2 = factories.EnterpriseGroupMembershipFactory()

        # mark enterprise group membership 2 to is_removed = True
        self.egm_2.is_removed = True
        self.egm_2.save()

    def test_get_queryset(self):
        """
        Test that the get_queryset method optimizes query by using select_related and only selecting specified fields.
        """
        request = RequestFactory().get("/")
        # ROUND 1 - set `is_removed__exact` = False
        request.GET = {'is_removed__exact': False}
        queryset = self.admin.get_queryset(request)
        results = list(queryset)

        # should only return the non-removed results
        self.assertEqual(len(results), 1)
        result_egm = results[0]
        self.assertEqual(self.egm_1.uuid, result_egm.uuid)
        # ensure is_removed = True, i.e. matching egm_1
        self.assertEqual(self.egm_1.is_removed, result_egm.is_removed)

        # ROUND 2 - set `is_removed__exact` = True
        request.GET = {'is_removed__exact': True}
        queryset = self.admin.get_queryset(request)
        results = list(queryset)

        # should return both results
        self.assertEqual(len(results), 2)
        # is_removed value should differ between the two results
        self.assertNotEqual(results[0].is_removed, results[1].is_removed)
