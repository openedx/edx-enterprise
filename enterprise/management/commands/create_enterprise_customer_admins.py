"""
Management command to create EnterpriseCustomerAdmin records for users with the enterprise_admin role.

This command will:
1. Find all users with the enterprise_admin role
2. For each user:
   - If they are an internal staff user (has a SystemWideEnterpriseUserRoleAssignment with applies_to_all_contexts=True):
     - Get all active enterprises
     - Create EnterpriseCustomerUser records for each enterprise if they don't exist
     - Create EnterpriseCustomerAdmin records for each enterprise
   - Otherwise:
     - Create a single EnterpriseCustomerAdmin record for their specific enterprise
3. Skip any users that already have EnterpriseCustomerAdmin records
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerAdmin,
    EnterpriseCustomerUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import batch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Create EnterpriseCustomerAdmin records for users with the enterprise_admin role.
    """
    help = 'Creates EnterpriseCustomerAdmin records for users with the enterprise_admin role'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--batch-size',
            action='store',
            dest='batch_size',
            default=500,
            help='Number of role assignments to process in each batch.',
            type=int,
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        if dry_run:
            self.stdout.write('DRY RUN - No changes will be made')

        # Get all users with the enterprise_admin role
        admin_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role__name='enterprise_admin'
        ).select_related('user', 'enterprise_customer')

        # Process assignments in batches
        for role_assignments_batch in batch(admin_role_assignments, batch_size=batch_size):
            for role_assignment in role_assignments_batch:
                user = role_assignment.user
                enterprise_user = EnterpriseCustomerUser.objects.filter(
                    user_id=user.id,
                    enterprise_customer=role_assignment.enterprise_customer
                ).first()
                if enterprise_user:
                    self._create_admin_record(enterprise_user, dry_run)

    def _create_admin_record(self, enterprise_user, dry_run):
        """
        Create an EnterpriseCustomerAdmin record for the given EnterpriseCustomerUser if one doesn't exist.
        """
        if not EnterpriseCustomerAdmin.objects.filter(enterprise_customer_user=enterprise_user).exists():
            if dry_run:
                self.stdout.write(
                    f'Would create EnterpriseCustomerAdmin for user {enterprise_user.user_email} '
                    f'and enterprise {enterprise_user.enterprise_customer.name}'
                )
            else:
                try:
                    with transaction.atomic():
                        EnterpriseCustomerAdmin.objects.create(
                            enterprise_customer_user=enterprise_user
                        )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created EnterpriseCustomerAdmin for user {enterprise_user.user_email} '
                            f'and enterprise {enterprise_user.enterprise_customer.name}'
                        )
                    )
                except Exception as e:
                    logger.error(
                        f'Error creating EnterpriseCustomerAdmin for user {enterprise_user.user_email} '
                        f'and enterprise {enterprise_user.enterprise_customer.name}: {str(e)}'
                    )
