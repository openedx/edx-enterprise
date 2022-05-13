"""
Management command for deleting all SystemWideEnterpriseUserRoleAssignment
when is_active = False
"""

import logging

from django.contrib import auth
from django.core.management.base import BaseCommand

from enterprise.models import SystemWideEnterpriseUserRoleAssignment
from enterprise.utils import batch

log = logging.getLogger(__name__)
User = auth.get_user_model()


# pylint: disable=logging-fstring-interpolation
class Command(BaseCommand):
    """
    Management command to delete all SystemWideEnterpriseUserRoleAssignment where is_active = False
    """
    help = """
    Delete all SystemWideEnterpriseUserRoleAssignment where is_active is False
    Example usage:
      ./manage.py lms delete_all_inactive_system_role_assignments
    """

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--batch-size',
            action='store',
            dest='batch_size',
            default=500,
            help='Number of user role asssignments to update in each batch of updates.',
            type=int,
        )

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        ras_to_delete = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            is_active=False,
        )
        record_count = ras_to_delete.count()

        batch_size = options['batch_size']
        log.info(
            f'Begin deleting inactive roleassignments batches of {batch_size}'
        )

        batch_number = 1
        for role_assignment_batch in batch(ras_to_delete, batch_size=batch_size):
            # Don't print everything, but give us a sense where we're at
            log.info(f"Now deleting batch number {batch_number}")
            for role_assignment in role_assignment_batch:
                # No bulk delete without raw sql, so this will do
                role_assignment.delete()
            batch_number += 1

        log.info(
            f'Done deleting {record_count} roleassignments.'
        )
