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
    Management command to copy `user_id` values to the foreign key `user_fk` field in the enterprise_customer_user table.

    Example usage:
        $ ./manage.py backfill_ecu_table_user_foreign_key
    """
    help = 'Goes through the Enterprise Customer User table in batches and copies the user_id to the user_fk foreign key.'

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

    def backfill_ecu_table_user_foreign_key(self, options):
        """
        Assigns enterprise_learner role to users.
        """
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']

        ecus = EnterpriseCustomerUser.objects.all().filter(user_fk__isnull=True)

        for ecu_batch in batch(ecus, batch_size=batch_limit):
            user_fk_updates = []
            for ecu in ecu_batch:
                log.info('Processing EnterpriseCustomerUser %s', ecu)

                ecu.user_fk = ecu.user_id
                user_fk_updates.append(ecu)

            if user_fk_updates:
                EnterpriseCustomerUser.objects.bulk_update(
                    user_fk_updates,
                    ['user_fk'],
                    batch_size=batch_limit # setting batch_size for extra safety
                )
                log.info('Updated %d EnterpriseCustomerUser records', len(user_fk_updates))

            sleep(batch_sleep)

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        log.info('Starting backfilling ECU user_fk field from user_id!')

        self.backfill_ecu_table_user_foreign_key(options)

        log.info('Successfully finished backfilling ECU user_fk field from user_id!')
