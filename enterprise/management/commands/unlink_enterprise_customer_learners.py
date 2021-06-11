# -*- coding: utf-8 -*-
"""
Django management command to unlink the learners, Delete the enrollments and remove the DSC.
"""
import csv
import logging

from django.contrib import auth
from django.core.management import BaseCommand

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerUser,
)
from enterprise.utils import delete_data_sharing_consent

LOGGER = logging.getLogger(__name__)

User = auth.get_user_model()


class Command(BaseCommand):
    """
    Django management command to unlink the learners, Delete the enrollments and remove the DSC

    Example usage:
    ./manage.py lms unlink_enterprise_customer_learners -e 22b783f5-e1d9-4228-87e4-5cf1cf110320 --data-csv path/file.csv
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

    def handle(self, *args, **options):
        csv_path = options['data_csv']
        enterprise_customer_uuid = options['enterprise_customer_uuid']
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)

        LOGGER.info('[Unlink and Remove DSC]  Process started.')

        results = {}

        with open(csv_path) as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                email = row['email']
                results[email] = {'Unlinked': None, 'Removed_DSC': None, 'Removed_EnterpriseCourseEnrolments': None}

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
                    continue

                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    continue

                # Fetch EnterpriseCourseEnrollments
                enterprise_course_enrollments = EnterpriseCourseEnrollment.objects.filter(
                    enterprise_customer_user__user_id=user.id,
                    enterprise_customer_user__enterprise_customer=enterprise_customer,
                )

                # Remove DSC
                course_ids = list(enterprise_course_enrollments.values_list('course_id', flat=True))
                for course_id in course_ids:
                    delete_data_sharing_consent(
                        course_id=course_id,
                        customer_uuid=enterprise_customer_uuid,
                        user_email=email,
                    )

                results[email]['Removed_DSC'] = course_ids

                # Delete the EnterpriseCourseEnrollments
                enterprise_course_enrollments.delete()
                results[email]['Removed_EnterpriseCourseEnrolments'] = course_ids

        LOGGER.info('[Unlink and Remove DSC] Execution completed for enterprise: %s, \nResults: %s',
                    enterprise_customer_uuid, results)
