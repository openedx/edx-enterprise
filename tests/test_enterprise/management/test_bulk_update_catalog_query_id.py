"""
Tests for the Django management command `create_enterprise_course_enrollments`.
"""

import ddt
from pytest import mark

from django.core.management import call_command
from django.test import TestCase

from enterprise.models import EnterpriseCustomerCatalog
from test_utils.factories import EnterpriseCatalogQueryFactory, EnterpriseCustomerCatalogFactory

EXCEPTION = "DUMMY_TRACE_BACK"


@mark.django_db
@ddt.ddt
class CreateEnterpriseCourseEnrollmentCommandTests(TestCase):
    """
    Test command `bulk_update_catalog_query_id`.
    """
    command = 'bulk_update_catalog_query_id'

    def setUp(self):
        self.enterprise_catalog_query_1 = EnterpriseCatalogQueryFactory()
        self.enterprise_catalog_query_2 = EnterpriseCatalogQueryFactory()
        self.enterprise_catalog_query_3 = EnterpriseCatalogQueryFactory()
        self.enterprise_catalog_1 = EnterpriseCustomerCatalogFactory(
            enterprise_catalog_query_id=self.enterprise_catalog_query_1.id
        )
        self.enterprise_catalog_2 = EnterpriseCustomerCatalogFactory(
            enterprise_catalog_query_id=self.enterprise_catalog_query_2.id
        )
        super().setUp()

    def test_bulk_query_update_only_changes_provided_query(self):
        """
        Test that the bulk_update_catalog_query_id command will only update enterprise catalogs who's
        enterprise_catalog_query_ids match the provided old_id value
        """
        call_command(self.command, old_id=self.enterprise_catalog_query_1.id, new_id=self.enterprise_catalog_query_3.id)
        assert EnterpriseCustomerCatalog.objects.filter(
            enterprise_catalog_query_id=self.enterprise_catalog_query_3.id
        ).first()
        assert EnterpriseCustomerCatalog.objects.filter(
            enterprise_catalog_query_id=self.enterprise_catalog_query_2.id
        ).first()
        assert not EnterpriseCustomerCatalog.objects.filter(
            enterprise_catalog_query_id=self.enterprise_catalog_query_1.id
        ).first()
