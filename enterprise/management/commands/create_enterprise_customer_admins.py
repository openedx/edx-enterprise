"""
Management command to create EnterpriseCustomerAdmin records for users with the enterprise_admin role.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from enterprise.models import EnterpriseCustomerAdmin, EnterpriseCustomerUser, SystemWideEnterpriseUserRoleAssignment
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
            logger.info('DRY RUN - No changes will be made')

        admin_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role__name='enterprise_admin'
        ).select_related('user', 'enterprise_customer')

        for role_assignments_batch in batch(admin_role_assignments, batch_size=batch_size):
            # Get all user IDs and enterprise customer IDs from this batch
            user_ids = [ra.user.id for ra in role_assignments_batch]
            enterprise_customer_uuids = [
                ra.enterprise_customer.uuid
                for ra in role_assignments_batch
                if ra.enterprise_customer is not None
            ]
            if not enterprise_customer_uuids:
                continue

            enterprise_users = EnterpriseCustomerUser.objects.filter(
                user_id__in=user_ids,
                enterprise_customer__uuid__in=enterprise_customer_uuids
            ).select_related('enterprise_customer')

            enterprise_user_map = {
                (eu.user_id, eu.enterprise_customer.uuid): eu
                for eu in enterprise_users
            }

            existing_admin_enterprise_user_ids = set(
                EnterpriseCustomerAdmin.objects.filter(
                    enterprise_customer_user__in=enterprise_users
                ).values_list('enterprise_customer_user_id', flat=True)
            )

            enterprise_users_to_create = []
            for role_assignment in role_assignments_batch:
                if role_assignment.enterprise_customer is None:
                    continue
                enterprise_user = enterprise_user_map.get(
                    (role_assignment.user.id, role_assignment.enterprise_customer.uuid)
                )
                if enterprise_user and enterprise_user.id not in existing_admin_enterprise_user_ids:
                    enterprise_users_to_create.append(enterprise_user)

            if enterprise_users_to_create:
                if dry_run:
                    for enterprise_user in enterprise_users_to_create:
                        logger.info(
                            f'Would create EnterpriseCustomerAdmin for user {enterprise_user}'
                        )
                else:
                    try:
                        with transaction.atomic():
                            admin_records = [
                                EnterpriseCustomerAdmin(enterprise_customer_user=eu)
                                for eu in enterprise_users_to_create
                            ]
                            EnterpriseCustomerAdmin.objects.bulk_create(admin_records)

                            for enterprise_user in enterprise_users_to_create:
                                logger.info(
                                    f'Created EnterpriseCustomerAdmin for user {enterprise_user}'
                                )
                    except Exception as e:  # pylint: disable=broad-except
                        logger.error(
                            f'Error creating EnterpriseCustomerAdmin records: {str(e)}'
                        )
