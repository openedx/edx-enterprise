"""
Django management command to Fix DSC records having spaces in there course Id.
"""
import logging

from edx_django_utils.db import chunked_queryset

from django.core.management import BaseCommand

from consent.models import DataSharingConsent

LOGGER = logging.getLogger(__name__)
MESSAGE_FORMAT = 'DSC enterprise: {}, username: {}, course_id: {}'


class Command(BaseCommand):
    """
    Django management command to Fix DSC records having spaces in there course Id.

    This Command fixes the DSC records what were saved due to bug in our system and DSC records were saved with spaces.

    Example usage:
    ./manage.py lms fix_dsc_records
    ./manage.py lms fix_dsc_records --no-commit
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        LOGGER.info('[Fix DSC Records]  Process started.')

        results = {
            'Fixed Record Count': 0,
            'Deleted Record Count': 0,
            'Fixed Records': [],
            'Deleted Records': [],
        }
        dsc_records = DataSharingConsent.objects.filter(course_id__contains=' ')
        LOGGER.info('[Fix DSC Records]  {} records to be fixed'.format(dsc_records.count()))
        for chunked_dsc_records in chunked_queryset(dsc_records):
            for dsc in chunked_dsc_records:
                fixed_dsc_course_id = dsc.course_id.replace(' ', '+')
                existing_fixed_record = DataSharingConsent.objects.filter(
                    enterprise_customer=dsc.enterprise_customer, username=dsc.username, course_id=fixed_dsc_course_id
                )
                message = MESSAGE_FORMAT.format(dsc.enterprise_customer, dsc.username, dsc.course_id)
                if existing_fixed_record.exists():
                    if should_commit:
                        dsc.delete()
                    results['Deleted Records'].append(message)
                    results['Deleted Record Count'] += 1
                else:
                    if should_commit:
                        dsc.course_id = fixed_dsc_course_id
                        dsc.save()
                    results['Fixed Records'].append(message)
                    results['Fixed Record Count'] += 1

        LOGGER.info('[Fix DSC Records] Execution completed.\nResults: {}'.format(results))
