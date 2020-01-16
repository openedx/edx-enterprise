# -*- coding: utf-8 -*-
"""
Reset SAPSF learner transmissions between two dates.
"""
from __future__ import absolute_import, unicode_literals

from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.translation import ugettext as _


class Command(BaseCommand):
    """
    Management command which resets SAPSF learner course completion data between two dates.
    That would allow us to resend course completion data.

    `./manage.py lms reset_sapsf_learner_transmissions
    --start_datetime=2020-01-14T00:00:00Z --end_datetime=2020-01-14T15:11:00Z`
    """
    help = _('''
    Reset SAPSF learner transmissions for the given EnterpriseCustomer and Channel between two dates.
    ''')

    def add_arguments(self, parser):
        """
        Add required --start_datetime and --end_datetime arguments to the parser.
        """
        parser.add_argument(
            '--start_datetime',
            dest='start_datetime',
            required=True,
            help=_('Start date and time in YYYY-MM-DDTHH:MM:SSZ format.'),
        )

        parser.add_argument(
            '--end_datetime',
            dest='end_datetime',
            required=True,
            help=_('End date and time in YYYY-MM-DDTHH:MM:SSZ format.'),
        )

        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        """
        Resets SAPSF learner course completion data between two dates.
        """
        start_datetime = parse_datetime(options['start_datetime'])
        end_datetime = parse_datetime(options['end_datetime'])

        if not start_datetime or not end_datetime:
            self.stdout.write(self.style.ERROR("FAILED: start or end dates times are not valid"))
            return

        SapSuccessFactorsLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'sap_success_factors',
            'SapSuccessFactorsLearnerDataTransmissionAudit'
        )
        enrollment_ids = SapSuccessFactorsLearnerDataTransmissionAudit.objects.filter(
            created__gte=start_datetime, created__lte=end_datetime
        ).values_list('enterprise_course_enrollment_id', flat=True)

        for enrollment_id in enrollment_ids:
            SapSuccessFactorsLearnerDataTransmissionAudit.objects.filter(
                enterprise_course_enrollment_id=enrollment_id,
                error_message=''
            ).update(error_message='Invalid data sent', status='400')
            self.stdout.write(
                self.style.SUCCESS('Successfully updated transmissions with these enrollment id ["%s"]' % enrollment_id)
            )
