"""
Backfill missing audit record foreign keys.
"""
import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardLearnerAssessmentDataTransmissionAudit,
    BlackboardLearnerDataTransmissionAudit,
)
from integrated_channels.canvas.models import (
    CanvasEnterpriseCustomerConfiguration,
    CanvasLearnerAssessmentDataTransmissionAudit,
    CanvasLearnerDataTransmissionAudit,
)
from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.degreed2.models import (
    Degreed2EnterpriseCustomerConfiguration,
    Degreed2LearnerDataTransmissionAudit,
)
from integrated_channels.degreed.models import (
    DegreedEnterpriseCustomerConfiguration,
    DegreedLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    GenericEnterpriseCustomerPluginConfiguration,
    GenericLearnerDataTransmissionAudit,
)
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration, MoodleLearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SapSuccessFactorsLearnerDataTransmissionAudit,
)

MODELS = {
    'MOODLE': [MoodleEnterpriseCustomerConfiguration, MoodleLearnerDataTransmissionAudit],
    'CSOD': [CornerstoneEnterpriseCustomerConfiguration, CornerstoneLearnerDataTransmissionAudit],
    'BLACKBOARD': [BlackboardEnterpriseCustomerConfiguration, BlackboardLearnerDataTransmissionAudit],
    'BLACKBOARD_ASMT': [BlackboardEnterpriseCustomerConfiguration, BlackboardLearnerAssessmentDataTransmissionAudit],
    'CANVAS': [CanvasEnterpriseCustomerConfiguration, CanvasLearnerDataTransmissionAudit],
    'CANVAS_ASMT': [CanvasEnterpriseCustomerConfiguration, CanvasLearnerAssessmentDataTransmissionAudit],
    'DEGREED': [DegreedEnterpriseCustomerConfiguration, DegreedLearnerDataTransmissionAudit],
    'DEGREED2': [Degreed2EnterpriseCustomerConfiguration, Degreed2LearnerDataTransmissionAudit],
    'GENERIC': [GenericEnterpriseCustomerPluginConfiguration, GenericLearnerDataTransmissionAudit],
    'SAP': [SAPSuccessFactorsEnterpriseCustomerConfiguration, SapSuccessFactorsLearnerDataTransmissionAudit],
}

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Management command which backfills missing audit record foreign keys.
    """
    help = _('''
    Set error state for configurations.
    ''')

    def update_config_last_errored_at(self):
        """
        For each audit record kind (learner and content), find all the records in batch, and lookup
        if they've had recent sync errors in the last day. If not, clear out the last_content_sync_errored_at
        value associated with the configuration.
        """
        try:
            has_learner_errors, has_content_errors = True, True
            yesterday = datetime.now() - timedelta(days=1)
            for channel_code, (ConfigModel, LearnerAuditModel) in MODELS.items():
                configs = ConfigModel.objects.all().filter()
                for config in configs:
                    if config.last_sync_errored_at is None:
                        continue
                    customer_uuid = config.enterprise_customer.uuid
                    plugin_id = config.id

                    errored_learner_audits = LearnerAuditModel.objects.filter(
                        created__date__gt=yesterday,
                        status__gt=299,
                        enterprise_customer_uuid=customer_uuid,
                        plugin_configuration_id=plugin_id,
                    )
                    if not errored_learner_audits:
                        config.last_learner_sync_errored_at = None
                        has_learner_errors = False

                    errored_content_audits = ContentMetadataItemTransmission.objects.filter(
                        remote_created_at__gt=yesterday,
                        enterprise_customer=config.enterprise_customer,
                        integrated_channel_code=channel_code,
                        plugin_configuration_id=plugin_id,
                        api_response_status_code__gt=299
                    )
                    if not errored_content_audits:
                        config.last_content_sync_errored_at = None
                        has_content_errors = False

                    if not has_learner_errors and not has_content_errors:
                        config.last_sync_errored_at = None
                    config.save()
        except Exception as exc:
            LOGGER.exception('backfill_missing_foreign_keys failed', exc_info=exc)
            raise exc

    def handle(self, *args, **options):
        """
        Set error state for configurations.
        """
        self.update_config_last_errored_at()
