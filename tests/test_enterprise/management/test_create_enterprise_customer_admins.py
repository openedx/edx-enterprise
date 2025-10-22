"""
Tests for the Django management command `create_enterprise_customer_admins`.
"""

import logging

from pytest import mark
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

from enterprise import roles_api
from enterprise.models import EnterpriseCustomerAdmin, SystemWideEnterpriseUserRoleAssignment
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class CreateEnterpriseCustomerAdminsCommandTests(TestCase):
    """
    Test command `create_enterprise_customer_admins`.
    """
    command = 'create_enterprise_customer_admins'

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Test Enterprise',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )
        self.role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.create(
            user=self.user,
            role=roles_api.admin_role(),
            enterprise_customer=self.enterprise_customer
        )
        super().setUp()

    def test_dry_run_creates_no_records(self):
        """
        Test that dry run shows what would be created but doesn't create records.
        """
        with LogCapture(level=logging.INFO) as log_capture:
            call_command(self.command, '--dry-run')

            assert EnterpriseCustomerAdmin.objects.count() == 0

            expected_msg = (
                f'Would create EnterpriseCustomerAdmin for user {self.enterprise_customer_user}'
            )
            assert any(expected_msg in record.getMessage() for record in log_capture.records)

    def test_creates_admin_records(self):
        """
        Test that the command creates EnterpriseCustomerAdmin records.
        """
        with LogCapture(level=logging.INFO) as log_capture:
            call_command(self.command)

            assert EnterpriseCustomerAdmin.objects.count() == 1
            admin_record = EnterpriseCustomerAdmin.objects.first()
            assert admin_record.enterprise_customer_user == self.enterprise_customer_user

            expected_msg = f'Created EnterpriseCustomerAdmin for user {self.enterprise_customer_user}'
            assert any(expected_msg in record.getMessage() for record in log_capture.records)
