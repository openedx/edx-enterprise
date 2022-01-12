"""
Django management command for creating DataSharingConsent records.
"""
import csv
import logging

from django.core.management import BaseCommand

from consent.models import DataSharingConsent
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command for creating DataSharingConsent records
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-csv',
            action='store',
            dest='data_csv',
            default=None,
            help='Path of csv to read enterprise learner data',
            type=str,
        )

    def handle(self, *args, **options):
        csv_path = options['data_csv']

        LOGGER.info('Started creation of DSC records')

        with open(csv_path) as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                course_id = row['COURSE_ID']
                enterprise_uuid = row['ENTERPRISE_UUID']
                username = row['USERNAME']

                enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.filter(
                    course_id=course_id,
                    enterprise_customer_user__user_id=row['USER_ID'],
                    enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
                ).exists()
                if enterprise_course_enrollment:
                    enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_uuid)
                    DataSharingConsent.objects.update_or_create(
                        username=username,
                        course_id=course_id,
                        enterprise_customer=enterprise_customer,
                        defaults={
                            'granted': True
                        },
                    )
                    LOGGER.info('DSC record created. User: [%s], Course: [%s]', username, course_id)

        LOGGER.info('Finished creation of DSC records')
