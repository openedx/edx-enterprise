"""
Management command for assigning enterprise_learner roles
to existing linked enterprise users that are missing them.
"""

import logging
from time import sleep

from django.contrib import auth
from django.core.management.base import BaseCommand

from enterprise.constants import ENTERPRISE_LEARNER_ROLE
from enterprise.models import EnterpriseCustomerUser, SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment
from enterprise.utils import batch

log = logging.getLogger(__name__)
User = auth.get_user_model()


class Command(BaseCommand):
    """
    Management command for assigning enterprise_learner roles to existing enterprise users.

    Example usage:
        $ ./manage.py backfill_learner_role_assignments
    """
    help = 'Assigns enterprise_learner role to linked enterprise users missing them.'

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=250,
            help='Number of records in each batch.',
            type=int,
        )

        parser.add_argument(
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=5,
            help='How long to sleep between batches.',
            type=int,
        )

    def backfill_learner_role_assignments(self, options):
        """
        Assigns enterprise_learner role to users.
        """
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']

        role = SystemWideEnterpriseRole.objects.get(name=ENTERPRISE_LEARNER_ROLE)
        ecus = EnterpriseCustomerUser.objects.select_related('enterprise_customer').filter(linked=True)

        for ecu_batch in batch(ecus, batch_size=batch_limit):
            for ecu in ecu_batch:
                log.info('Processing EnterpriseCustomerUser %s', ecu)

                user = User.objects.get(id=ecu.user_id)
                enterprise_customer = ecu.enterprise_customer

                role_assignment, created = SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
                    user=user,
                    role=role,
                    enterprise_customer=enterprise_customer
                )

                if created:
                    log.info(
                        'Created SystemWideEnterpriseUserRoleAssignment %s for enterprise user %s',
                        role_assignment, ecu
                    )
                else:
                    log.info(
                        'Did not create role assignment for enterprise user %s', ecu
                    )

            sleep(batch_sleep)

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        log.info('Starting assigning enterprise_learner roles to users!')

        self.backfill_learner_role_assignments(options)

        log.info('Successfully finished assigning enterprise_learner roles to users!')
