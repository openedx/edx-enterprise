"""
Management command for assigning enterprise_learner roles
to existing linked enterprise users that are missing them.
"""

import logging
from time import sleep

from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db import transaction, DatabaseError

from enterprise.models import EnterpriseCustomerUser
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
            '--max-retries',
            action='store',
            dest='max_retries',
            default=5,
            help='Max retries for each batch.',
            type=int,
        )
        parser.add_argument(
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=2,
            help='How long to sleep between batches.',
            type=int,
        )

    def safe_bulk_update(self, entries, max_retries, batch_limit):
        """Performs bulk_update with retry logic."""
        count = entries.count()
        for attempt in range(1, max_retries + 1):
            try:
                with transaction.atomic():
                    EnterpriseCustomerUser.objects.bulk_update(
                        entries, ['user_fk']
                    )
                return count
            except DatabaseError as e:
                wait_time = 2 ** attempt
                log.warning(f"Attempt {attempt}/{max_retries} failed: {e}. Retrying in {wait_time}s.")
                sleep(wait_time)
        raise Exception(f"Bulk update failed after {max_retries} retries.")

    def backfill_ecu_table_user_foreign_key(self, options):
        """
        Backfills user_fk from user_id in batches with timeout, retries, and progress reporting.
        """
        batch_limit = options.get('batch_limit', 250)
        batch_sleep = options.get('batch_sleep', 2)
        max_retries = options.get('max_retries', 5)

        total_rows = EnterpriseCustomerUser.objects.filter(user_fk__isnull=True).count()
        log.info(f"Starting backfill of {total_rows} rows in batches of {batch_limit}...")

        queryset = EnterpriseCustomerUser.objects.filter(user_fk__isnull=True)
        total_processed = 0
        print('queryset: ', queryset)

        while queryset.exists():
            ecu_batch = queryset[:batch_limit]

            for ecu in ecu_batch:
                log.info(f"Processing EnterpriseCustomerUser {ecu.id}")
                ecu.user_fk = ecu.user_id

            count = self.safe_bulk_update(ecu_batch, max_retries, batch_limit)
            total_processed += count
            log.info(f"Processed {total_processed}/{total_rows} rows.")
            sleep(batch_sleep)

        log.info(f"Backfill complete! Processed {total_processed}/{total_rows} records.")


    def handle(self, **options):
        """
        Entry point for management command execution.
        """
        log.info('Starting backfilling ECU user_fk field from user_id!')

        self.backfill_ecu_table_user_foreign_key(options)

        log.info('Successfully finished backfilling ECU user_fk field from user_id!')
