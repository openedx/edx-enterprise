
"""
Mark already transmitted LearnerDataTransmission as is_trasmitted=True for all integrated channels
"""

from logging import getLogger

from django.apps import apps
from django.core.management.base import BaseCommand

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin

LOGGER = getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Mark already transmitted LearnerDataTransmission as is_trasmitted=True for all integrated channels
    """

    def handle(self, *args, **options):
        """
        Mark already transmitted LearnerDataTransmission as is_trasmitted=True
        """
        channel_learner_audit_models = [
            ('moodle', 'MoodleLearnerDataTransmissionAudit'),
            ('blackboard', 'BlackboardLearnerDataTransmissionAudit'),
            ('blackboard', 'BlackboardLearnerAssessmentDataTransmissionAudit'),
            ('canvas', 'CanvasLearnerDataTransmissionAudit'),
            ('degreed2', 'Degreed2LearnerDataTransmissionAudit'),
            ('degreed', 'DegreedLearnerDataTransmissionAudit'),
            ('sap_success_factors', 'SapSuccessFactorsLearnerDataTransmissionAudit'),
            ('cornerstone', 'CornerstoneLearnerDataTransmissionAudit'),
            ('canvas', 'CanvasLearnerAssessmentDataTransmissionAudit'),
        ]
        for app_label, model_name in channel_learner_audit_models:
            model_class = apps.get_model(app_label=app_label, model_name=model_name)
            LOGGER.info(
                f'Started: setting {model_name}.is_transmitted set to True'
            )
            model_class.objects.filter(
                error_message='',
                status__lt=400,
            ).update(is_transmitted=True)

            LOGGER.info(
                f'Finished: setting {model_name}.is_transmitted set to True'
            )
