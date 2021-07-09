# -*- coding: utf-8 -*-
"""
Django management command to unlink the learners, Delete the enrollments and remove the DSC.
"""
import csv
import logging

from edx_django_utils.cache import TieredCache, get_cache_key

from django.contrib import auth
from django.core.management import BaseCommand

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, PendingEnterpriseCustomerUser

LOGGER = logging.getLogger(__name__)

User = auth.get_user_model()


class Command(BaseCommand):
    """
    Django management command to unlink the learners, Delete the enrollments and remove the DSC

    Example usage:
    ./manage.py lms unlink_enterprise_customer_learners -e <enterprise-uuid> --data-csv /path/file.csv
    ./manage.py lms unlink_enterprise_customer_learners -e <enterprise-uuid> --data-csv /path/file.csv --skip-unlink

    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-csv',
            action='store',
            dest='data_csv',
            help='Path of csv to read emails to be unlinked.',
            type=str,
        )

        parser.add_argument(
            '-e',
            '--enterprise_customer_uuid',
            action='store',
            dest='enterprise_customer_uuid',
            help='Run this command for only the given EnterpriseCustomer UUID.'
        )

        parser.add_argument(
            '--skip-unlink',
            action='store_true',
            dest='skip_unlink',
            default=False,
            help='Specify to remove the DSC without unlinking learner for given data_csv.'
        )

    def handle(self, *args, **options):
        csv_path = options['data_csv']
        skip_unlink = options['skip_unlink']
        enterprise_customer_uuid = options['enterprise_customer_uuid']
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)

        LOGGER.info('[Unlink and Remove DSC]  Process started.')

        results = {}

        with open(csv_path) as csv_file:
            rows = list(csv.DictReader(csv_file))
        csv_file.close()

        for row in rows:
            email = row['email']
            results[email] = {'Unlinked': None, 'Removed_DSC': None}

            if not skip_unlink:
                # Unlink the user.
                try:
                    EnterpriseCustomerUser.objects.unlink_user(
                        enterprise_customer=enterprise_customer, user_email=email
                    )
                    results[email]['Unlinked'] = 'Success'
                except (EnterpriseCustomerUser.DoesNotExist, PendingEnterpriseCustomerUser.DoesNotExist):
                    message = 'Email {email} is not associated with Enterprise Customer {ec_name}'.format(
                        email=email, ec_name=enterprise_customer.name
                    )
                    results[email]['Unlinked'] = message

            # Deleting the DSC record.
            try:
                user = User.objects.get(email=email)
                enterprise_customer_user = EnterpriseCustomerUser.all_objects.get(
                    enterprise_customer__uuid=enterprise_customer_uuid,
                    user_id=user.id
                )
                data_sharing_consent_records = enterprise_customer_user.data_sharing_consent_records
                course_ids = list(data_sharing_consent_records.values_list('course_id', flat=True))
                data_sharing_consent_records.delete()
                # Deleting the DCS cache
                for course_id in course_ids:
                    consent_cache_key = get_cache_key(
                        type='data_sharing_consent_needed',
                        user_id=user.id,
                        course_id=course_id
                    )
                    TieredCache.delete_all_tiers(consent_cache_key)
                results[email]['Removed_DSC'] = course_ids
            except (User.DoesNotExist, EnterpriseCustomerUser.DoesNotExist) as excep:
                results[email]['Removed_DSC'] = str(excep)

        LOGGER.info('[Unlink and Remove DSC] Execution completed for enterprise: %s, \nResults: %s',
                    enterprise_customer_uuid, results)
