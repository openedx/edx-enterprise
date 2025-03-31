"""
Management command for assigning enterprise_learner roles
to existing linked enterprise users that are missing them.
"""

import logging
from time import sleep

from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db import DatabaseError, models, transaction

from enterprise.models import EnterpriseCustomerUser
from integrated_channels.utils import batch_by_pk

log = logging.getLogger(__name__)
User = auth.get_user_model()


def safe_bulk_update(entries, properties, max_retries, manager):
    """Performs bulk_update with retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            with transaction.atomic():
                manager.bulk_update(
                    entries, properties
                )
            return len(entries)
        except DatabaseError as e:
            wait_time = 2 ** attempt
            log.warning(f"Attempt {attempt}/{max_retries} failed: {e}. Retrying in {wait_time}s.")
            sleep(wait_time)

    raise Exception(f"Bulk update failed after {max_retries} retries.")


def _fetch_and_update_in_batches(manager, batch_limit, batch_sleep, max_retries, ModelClass):
    """
    Fetches and updates records in batches.
    Only loads and updates a subset of records at a time to avoid memory and performance issues.
    Note: you cannot use django's queryset.iterator() method
    as MySQL does not support it and will still load everything into memory.
    """
    batch_counter = 1
    total_processed = 0

    for batch in batch_by_pk(
        ModelClass,
        extra_filter=models.Q(user_fk__isnull=True),
        batch_size=batch_limit,
        model_manager=manager,
    ):
        log.info(f"Processing batch {batch_counter}...")
        for ecu in batch:
            if isinstance(ModelClass._meta.get_field('user_fk'), models.ForeignKey):
                ecu.user_fk_id = ecu.user_id
            else:
                ecu.user_fk = ecu.user_id
        safe_bulk_update(batch, ['user_fk'], max_retries, manager=manager)
        total_processed += len(batch)
        log.info(f'Processed {total_processed} records.')
        sleep(batch_sleep)
        batch_counter += 1

    log.info(f"Final batch processed. Total {total_processed} records updated.")
    return True


class Command(BaseCommand):
    """
    Management command to copy `user_id` values to the foreign key `user_fk` field
    in the enterprise_customer_user table.

    Example usage:
        $ ./manage.py backfill_ecu_table_user_foreign_key
    """
    help = '''
    Goes through the Enterprise Customer User table in batches
    and copies the user_id to the user_fk foreign key.
    '''

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
            default=0.1,
            help='How long to sleep between batches.',
            type=float,
        )

    def backfill_ecu_table_user_foreign_key(self, options):
        """
        Backfills user_fk from user_id in batches with timeout, retries, and progress reporting.
        """
        batch_limit = options.get('batch_limit', 250)
        max_retries = options.get('max_retries', 5)
        batch_sleep = options.get('batch_sleep', 0.1)

        _fetch_and_update_in_batches(
            manager=EnterpriseCustomerUser.all_objects,
            batch_limit=batch_limit,
            batch_sleep=batch_sleep,
            max_retries=max_retries,
            ModelClass=EnterpriseCustomerUser,
        )

        _fetch_and_update_in_batches(
            manager=EnterpriseCustomerUser.history,
            batch_limit=batch_limit,
            batch_sleep=batch_sleep,
            max_retries=max_retries,
            ModelClass=EnterpriseCustomerUser,
        )

    def handle(self, *_args, **options):
        """
        Entry point for management command execution.
        """
        log.info('Starting backfilling ECU user_fk field from user_id!')

        self.backfill_ecu_table_user_foreign_key(options)

        log.info('Successfully finished backfilling ECU user_fk field from user_id!')
