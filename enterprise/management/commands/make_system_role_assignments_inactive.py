"""
Management command to set is_active to False for any SystemWideEnterpriseUserRoleAssignment
that have a null enterprise_customer_uuid and False applies_to_all_contexts
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
    Management command to set is_active to False for any SystemWideEnterpriseUserRoleAssignment
    that have a null enterprise_customer_uuid and False applies_to_all_contexts
    """
    help = """
    Set is_active to False for any SystemWideEnterpriseUserRoleAssignment record that
    has a null enterprise_customer_uuid and False applies_to_all_contexts
      ./manage.py lms make_system_role_assignments_inactive
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

        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help=(
                'If set, no updates or creates will occur; will instead iterate over '
                'the assignments that would be modified or created'
            ),
        )

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        ras_to_inactivate = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=None,
            applies_to_all_contexts=False,
            is_active=True,
        )

        record_count = ras_to_inactivate.count()
        if options['dry_run']:
            log.info(f'Would have set {record_count} records is_active field to False.')
            return

        batch_size = options['batch_size']
        log.info(
            f'Begin setting roleassignments is_active to False in batches of {batch_size}'
        )

        for role_assignment_batch in batch(ras_to_inactivate, batch_size=batch_size):
            for role_assignment in role_assignment_batch:
                role_assignment.is_active = False
            ras_to_inactivate.bulk_update(role_assignment_batch, ['is_active'])

        log.info(
            f'Done setting {record_count} roleassignments record is_active to False.'
        )
