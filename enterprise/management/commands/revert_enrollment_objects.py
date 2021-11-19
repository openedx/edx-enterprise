"""
Management command for reverting revoked enrollment
related objects to a particular time.
"""


import logging
from datetime import datetime

from dateutil.tz import tzutc

from django.contrib import auth
from django.core.management.base import BaseCommand

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer

log = logging.getLogger(__name__)
User = auth.get_user_model()


class Command(BaseCommand):
    """
    Management command for reverting revoked enrollment related objects to a particular time.

    Example usage:
        $ ./manage.py revert_enrollment_objects --year 2021 --month 11 --day 17 --enterprise-customer-name test-co
    """
    help = 'Reverts revoked enrollment related objects to a particular time.'

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--year',
            action='store',
            dest='year',
            default=9999,
            help='Year of date',
            type=int,
        )
        parser.add_argument(
            '--month',
            action='store',
            dest='month',
            default=1,
            help='Month of date',
            type=int,
        )
        parser.add_argument(
            '--day',
            action='store',
            dest='day',
            default=0,
            help='Date of date',
            type=int,
        )
        parser.add_argument(
            '--hour',
            action='store',
            dest='hour',
            default=0,
            help='Hour of date',
            type=int,
        )
        parser.add_argument(
            '--minute',
            action='store',
            dest='minute',
            default=0,
            help='Minute of date',
            type=int,
        )
        parser.add_argument(
            '--second',
            action='store',
            dest='second',
            default=0,
            help='Second of date',
            type=int,
        )

        parser.add_argument(
            '--enterprise-customer-name',
            action='store',
            dest='enterprise_customer_name',
            help='Enterprise customer name',
            type=int,
        )

    def revert_enrollment_objects(self, options):
        """
        Revert all EnterpriseCourseEnrollment, LicensedEnterpriseCourseEnrollment, and "student" CourseEnrollment
        objects to the date provided, using the history table IF is_revoked = True on LicensedEnterpriseCourseEnrollment
        """
        # e.g. datetime(2021, 11, 18, 0, 0, tzinfo=tzutc())
        time_to_revert_to = datetime(
            options['year'],
            options['month'],
            options['day'],
            options['hour'],
            options['minute'],
            options['second'],
            tzinfo=tzutc()
        )

        ec = EnterpriseCustomer.objects.get(name=options['enterprise_customer_name'])
        ecus = ec.enterprise_customer_users.all()

        for ecu in ecus:
            eces = EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user=ecu,
                licensed_with__is_revoked=True,
                licensed_with__modified__gte=time_to_revert_to,
            )

            for enrollment in eces:
                student_course_enrollment = enrollment.course_enrollment
                student_course_enrollment.history.as_of(time_to_revert_to).save()

                licensed_enrollment = enrollment.licensed_with
                licensed_enrollment.history.as_of(time_to_revert_to).save()

                enrollment.history.as_of(time_to_revert_to).save()

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        log.info('Begin reverting enrollment objects back!')

        self.revert_enrollment_objects(options)

        log.info('Sucessfully reverted enrollment objects back!')
