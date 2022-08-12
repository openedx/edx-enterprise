"""
Backfill missing audit record foreign keys.
"""
import logging

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db.models import Q
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
from integrated_channels.utils import batch_by_pk

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
    Backfill missing audit record foreign keys.
    ''')

    def find_ent_cust(self, enrollment_id):
        """
        Given an enterprise_course_enrollment id, walk the joins to EnterpriseCustomer
        """
        EnterpriseCourseEnrollment = apps.get_model('enterprise', 'EnterpriseCourseEnrollment')
        EnterpriseCustomerUser = apps.get_model('enterprise', 'EnterpriseCustomerUser')
        EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')
        try:
            ece = EnterpriseCourseEnrollment.objects.get(pk=enrollment_id)
            ecu = EnterpriseCustomerUser.objects.get(pk=ece.enterprise_customer_user_id)
            ec = EnterpriseCustomer.objects.get(pk=ecu.enterprise_customer_id)
            return ec
        except ObjectDoesNotExist:
            return None

    def backfill_join_keys(self):
        """
        For each audit record kind, find all the records in batch, then lookup the appropriate
        enterprise_customer_uuid and/or plugin_config_id
        """
        try:
            for channel_code, (ConfigModel, LearnerAuditModel) in MODELS.items():
                LOGGER.info(f'{LearnerAuditModel.__name__}')
                # make reentrant ie pickup where we've left off in case the job needs to be restarted
                # only need to check plugin config OR enterprise customer uuid
                only_missing_ld_fks = Q(plugin_configuration_id__isnull=True)
                for audit_record_batch in batch_by_pk(LearnerAuditModel, extra_filter=only_missing_ld_fks):
                    for audit_record in audit_record_batch:
                        enterprise_customer = self.find_ent_cust(audit_record.enterprise_course_enrollment_id)
                        if enterprise_customer is None:
                            continue
                        # nobody currently has more than 1 config across all kinds
                        config = ConfigModel.objects.filter(enterprise_customer=enterprise_customer).first()
                        if config is None:
                            continue
                        LOGGER.info(f'{LearnerAuditModel.__name__} <{audit_record.pk}> '
                                    f'enterprise_customer_uuid={enterprise_customer.uuid}, '
                                    f'plugin_configuration_id={config.id}')
                        audit_record.enterprise_customer_uuid = enterprise_customer.uuid
                        audit_record.plugin_configuration_id = config.id
                        audit_record.save()
                # migrate the content_metadata for this channel code, the _AS ones will be empty, effectively a skip
                only_missing_cm_fks = Q(integrated_channel_code=channel_code, plugin_configuration_id__isnull=True)
                # make reentrant ie pickup where we've left off in case the job needs to be restarted
                for audit_record_batch in self.batch_by_pk(ContentMetadataItemTransmission, extra_filter=only_missing_cm_fks):  # pylint: disable=line-too-long
                    for audit_record in audit_record_batch:
                        if audit_record.enterprise_customer is None:
                            continue
                        config = ConfigModel.objects.filter(enterprise_customer=audit_record.enterprise_customer).first()  # pylint: disable=line-too-long
                        if config is None:
                            continue
                        LOGGER.info(f'ContentMetadataItemTransmission {channel_code} <{audit_record.pk}> '
                                    f'plugin_configuration_id={config.id}')
                        audit_record.plugin_configuration_id = config.id
                        audit_record.save()
        except Exception as exc:
            LOGGER.exception('backfill_missing_foreign_keys failed', exc_info=exc)
            raise exc

    def handle(self, *args, **options):
        """
        Backfill missing audit record foreign keys.
        """
        self.backfill_join_keys()
