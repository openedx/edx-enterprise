"""
Django management command to ensure there is at most a single EnterpriseCustomerUser
with `active=True` for each enterprise user.
"""
import logging
from time import sleep

from django.apps import apps
from django.core.management import BaseCommand
from django.db.models import Count

from enterprise.utils import batch

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to ensure there is at most a single EnterpriseCustomerUser
    with `active=True` for each enterprise user.

    Example usage:
    ./manage.py lms ensure_singular_active_enterprise_customer_user
    """

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=100,
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

    def _enterprise_customer_user_model(self):
        """ Returns `EnterpriseCustomerUser model """
        EnterpriseCustomerUser = apps.get_model(
            'enterprise',
            'EnterpriseCustomerUser',
        )
        return EnterpriseCustomerUser

    def _historical_enterprise_customer_user_model(self):
        """ Returns `HistoricalEnterpriseCustomerUser model """
        HistoricalEnterpriseCustomerUser = apps.get_model(
            'enterprise',
            'HistoricalEnterpriseCustomerUser',
        )
        return HistoricalEnterpriseCustomerUser

    def _process_user(self, user):
        """
        Finds all EnterpriseCustomerUser objects for the specified user, flipping all but one to
        have `active=False`. The one that is not flipped (remains `active=True`) is based on the
        historical records of which EnterpriseCustomerUser object was flipped to `active=True`
        most recently.
        """
        EnterpriseCustomerUser = self._enterprise_customer_user_model()
        HistoricalEnterpriseCustomerUser = self._historical_enterprise_customer_user_model()
        lms_user_id = user['user_id']
        current_active_ecu_count = user['ecu_count']
        log.info('Processing LMS User ID %s', lms_user_id)
        active_historical_ecus = HistoricalEnterpriseCustomerUser.objects.filter(user_id=lms_user_id, active=True)
        most_recent_active_ecu = active_historical_ecus.order_by('-history_date').first()
        ecus_for_user = EnterpriseCustomerUser.objects.filter(
            user_id=lms_user_id,
            active=True,
        ).exclude(
            id=most_recent_active_ecu.id,
        )
        for ecu in ecus_for_user:
            ecu.active = False
        EnterpriseCustomerUser.objects.bulk_update(ecus_for_user, ['active'])
        log.info(
            'Successfully updated %s of %s EnterpriseCustomerUser objects for LMS User ID %s',
            len(ecus_for_user),
            current_active_ecu_count,
            lms_user_id,
        )

    def handle(self, *args, **options):
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']

        EnterpriseCustomerUser = self._enterprise_customer_user_model()
        active_ecus = EnterpriseCustomerUser.objects.filter(active=True)
        user_ids_by_active_ecu_count = active_ecus.values('user_id').annotate(ecu_count=Count('user_id'))
        ordered_user_ids_by_active_ecu_count = user_ids_by_active_ecu_count.order_by('-ecu_count')
        user_ids_with_multiple_active_ecus = ordered_user_ids_by_active_ecu_count.filter(ecu_count__gt=1)

        log.info(
            'Found %s enterprise users with mulitple active EnterpriseCustomerUser objects',
            len(user_ids_with_multiple_active_ecus),
        )

        for user_batch in batch(user_ids_with_multiple_active_ecus, batch_size=batch_limit):
            for user in user_batch:
                self._process_user(user)
            sleep(batch_sleep)
