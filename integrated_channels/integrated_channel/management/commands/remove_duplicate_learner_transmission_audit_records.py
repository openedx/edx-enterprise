"""
Transmits consenting enterprise learner data to the integrated channels.
"""
from logging import getLogger

from django.apps import apps
from django.contrib import auth
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from django.utils.translation import gettext as _

User = auth.get_user_model()
LOGGER = getLogger(__name__)


class Command(BaseCommand):
    """
    Management command which removes the duplicated transmission audit records for integration channels
    """
    help = _('''
    Transmit Enterprise learner course completion data for the given EnterpriseCustomer.
    ''')

    def handle(self, *args, **options):
        """
        Remove the duplicated transmission audit records for integration channels.
        """
        # Multiple transmission records were being saved against single enterprise_course_enrollment_id in case
        # transmission fails against course and course run id. Job of this management command is to keep the latest
        # record for enterprise_course_enrollment_id that doesn't start with "course-v1: and delete all other records."
        channel_learner_audit_models = [
            ('moodle', 'MoodleLearnerDataTransmissionAudit'),
            ('blackboard', 'BlackboardLearnerDataTransmissionAudit'),
            ('canvas', 'CanvasLearnerDataTransmissionAudit'),
            ('degreed2', 'Degreed2LearnerDataTransmissionAudit'),
            ('sap_success_factors', 'SapSuccessFactorsLearnerDataTransmissionAudit'),
        ]
        for app_label, model_name in channel_learner_audit_models:
            model_class = apps.get_model(app_label=app_label, model_name=model_name)

            latest_records_without_prefix = (
                model_class.objects.exclude(course_id__startswith='course-v1:')
                .values('enterprise_course_enrollment_id').annotate(most_recent_transmission_id=Max('id'))
            )

            LOGGER.info(
                f'{app_label} channel has {latest_records_without_prefix.count()} records without prefix'
            )

            # Delete all duplicate records for each enterprise_course_enrollment_id
            with transaction.atomic():
                for entry in latest_records_without_prefix:
                    enterprise_course_enrollment_id = entry['enterprise_course_enrollment_id']
                    most_recent_transmission_id = entry['most_recent_transmission_id']

                    # Delete all records except the latest one without "course-v1:"
                    duplicate_records_to_delete = (
                        model_class.objects
                        .filter(enterprise_course_enrollment_id=enterprise_course_enrollment_id)
                        .exclude(id=most_recent_transmission_id)
                    )
                    LOGGER.info(
                        f'{app_label} channel - {duplicate_records_to_delete.count()} duplicate records are deleted '
                        f' for enrollment id {enterprise_course_enrollment_id}'
                    )
                    duplicate_records_to_delete.delete()
