"""
Tests for the Django management command `validate_default_enrollment_intentions`.
"""

import logging
from contextlib import nullcontext
from datetime import timedelta
from uuid import uuid4

import ddt
import mock
from edx_django_utils.cache import TieredCache
from freezegun.api import freeze_time
from pytest import mark, raises
from testfixtures import LogCapture

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from enterprise.models import EnterpriseCatalogQuery, EnterpriseCustomerCatalog
from test_utils.factories import DefaultEnterpriseEnrollmentIntentionFactory, EnterpriseCustomerCatalogFactory

NOW = timezone.now()


@mark.django_db
@ddt.ddt
class ValidateDefaultEnrollmentIntentionsCommandTests(TestCase):
    """
    Test command `validate_default_enrollment_intentions`.
    """
    command = "validate_default_enrollment_intentions"

    def setUp(self):
        self.catalog = EnterpriseCustomerCatalogFactory()
        self.catalog_query = self.catalog.enterprise_catalog_query
        self.customer = self.catalog.enterprise_customer
        self.content_key = "edX+DemoX"
        self.content_uuid = str(uuid4())

        # Add another catalog/customer/query with an intention that always gets skipped.
        self.other_catalog = EnterpriseCustomerCatalogFactory()

        # Add yet another catalog/customer/query without an intention just to spice things up.
        EnterpriseCustomerCatalogFactory()

        TieredCache.dangerous_clear_all_tiers()
        super().setUp()

    @ddt.data(
        # Totally happy case.
        {},
        # Happy-ish case (customer was skipped because catalog query was too new).
        {
            "catalog_query_modified": NOW - timedelta(minutes=29),
            "expected_logging": "0/2 were evaluated (2/2 skipped)",
        },
        # Happy-ish case (customer was skipped because catalog was too new).
        {
            "catalog_modified": NOW - timedelta(minutes=29),
            "expected_logging": "0/2 were evaluated (2/2 skipped)",
        },
        # Happy-ish case (customer was skipped because catalog was too new).
        # This version sets the catalog response to say content is not included, for good measure.
        {
            "catalog_modified": NOW - timedelta(minutes=29),
            "customer_content_metadata_api_success": False,
            "expected_logging": "0/2 were evaluated (2/2 skipped)",
        },
        # Sad case (content was not found in customer's catalogs).
        {
            "customer_content_metadata_api_success": False,
            "expected_logging": "0/1 passed validation (1/1 invalid).",
            "expected_command_error": "1 invalid default enrollment intentions found.",
        },
    )
    @ddt.unpack
    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @freeze_time(NOW)
    def test_validate_default_enrollment_intentions(
        self,
        mock_catalog_api_client,
        catalog_query_modified=NOW - timedelta(minutes=31),
        catalog_modified=NOW - timedelta(minutes=31),
        customer_content_metadata_api_success=True,
        expected_logging="1/2 were evaluated (1/2 skipped)",
        expected_command_error=False,
    ):
        """
        Test validating default enrollment intentions in cases where customers have
        varying ages of catalogs and content inclusion statuses.
        """
        mock_catalog_api_client.return_value = mock.Mock(
            get_content_metadata_content_identifier=mock.Mock(
                return_value={
                    "content_type": "course",
                    "key": self.content_key,
                    "course_runs": [{
                        "uuid": self.content_uuid,
                        "key": f"course-v1:{self.content_key}+run",
                    }],
                    "advertised_course_run_uuid": self.content_uuid,
                },
            ),
            get_customer_content_metadata_content_identifier=mock.Mock(
                return_value={
                    "content_type": "course",
                    "key": self.content_key,
                    "course_runs": [{
                        "uuid": self.content_uuid,
                        "key": f"course-v1:{self.content_key}+run",
                    }],
                    "advertised_course_run_uuid": self.content_uuid,
                } if customer_content_metadata_api_success else {},
            ),
        )
        # This intention is subject to variable test inputs.
        self.catalog_query.modified = catalog_query_modified
        EnterpriseCatalogQuery.objects.bulk_update([self.catalog_query], ["modified"])  # bulk_update() avoids signals.
        self.catalog.modified = catalog_modified
        EnterpriseCustomerCatalog.objects.bulk_update([self.catalog], ["modified"])  # bulk_update() avoids signals.
        DefaultEnterpriseEnrollmentIntentionFactory(
            enterprise_customer=self.customer,
            content_key=self.content_key,
        )
        # This intention should always be skipped.
        DefaultEnterpriseEnrollmentIntentionFactory(
            enterprise_customer=self.other_catalog.enterprise_customer,
            content_key=self.content_key,
        )
        cm = raises(CommandError) if expected_command_error else nullcontext()
        with LogCapture(level=logging.INFO) as log_capture:
            with cm:
                call_command(self.command, delay_minutes=30)
        logging_messages = [log_msg.getMessage() for log_msg in log_capture.records]
        assert any(expected_logging in message for message in logging_messages)
