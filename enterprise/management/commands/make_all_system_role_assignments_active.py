"""
Management command for making all SystemWideEnterpriseUserRoleAssignment
active. This is a way to revert all changes from make_system_role_assignments_inactive.
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
    Management command to make is_active on all SystemWideEnterpriseUserRoleAssignment True
    """
    help = """
    Set is_active to True for all SystemWideEnterpriseUserRoleAssignment
    Example usage:
      ./manage.py lms make_all_system_role_assignments_active
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
        ras_to_activate = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            is_active=False,
        )
        record_count = ras_to_activate.count()

        batch_size = options['batch_size']
        log.info(
            f'Begin setting roleassignments is_active to True in batches of {batch_size}'
        )

        for role_assignment_batch in batch(ras_to_activate, batch_size=batch_size):
            for role_assignment in role_assignment_batch:
                role_assignment.is_active = True
            ras_to_activate.bulk_update(role_assignment_batch, ['is_active'])

        log.info(
            f'Done setting {record_count} roleassignments record is_active to True.'
        )
