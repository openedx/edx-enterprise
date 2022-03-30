"""
Backfill missing audit record foreign keys.
"""
import logging

from django.apps import apps
from django.contrib import auth
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardLearnerAssessmentDataTransmissionAudit,
)
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration, CanvasLearnerDataTransmissionAudit
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
    'BLACKBOARD': [BlackboardEnterpriseCustomerConfiguration, BlackboardLearnerAssessmentDataTransmissionAudit],
    'CANVAS': [CanvasEnterpriseCustomerConfiguration, CanvasLearnerDataTransmissionAudit],
    'CSOD': [CornerstoneEnterpriseCustomerConfiguration, CornerstoneLearnerDataTransmissionAudit],
    'DEGREED': [DegreedEnterpriseCustomerConfiguration, DegreedLearnerDataTransmissionAudit],
    'DEGREED2': [Degreed2EnterpriseCustomerConfiguration, Degreed2LearnerDataTransmissionAudit],
    'GENERIC': [GenericEnterpriseCustomerPluginConfiguration, GenericLearnerDataTransmissionAudit],
    'MOODLE': [MoodleEnterpriseCustomerConfiguration, MoodleLearnerDataTransmissionAudit],
    'SAP': [SAPSuccessFactorsEnterpriseCustomerConfiguration, SapSuccessFactorsLearnerDataTransmissionAudit],
}

LOGGER = logging.getLogger(__name__)

User = auth.get_user_model()


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Management command which backfills missing audit record foreign keys.
    """
    help = _('''
    Backfill missing audit record foreign keys.
    ''')
    stealth_options = ('enterprise_customer_slug', 'user1', 'user2')

    def add_arguments(self, parser):
        """
        Add required --api_user argument to the parser.
        """
        parser.add_argument(
            '--api_user',
            dest='api_user',
            required=True,
            metavar='LMS_API_USERNAME',
            help=_('Username of a user authorized to fetch grades from the LMS API.'),
        )
        super().add_arguments(parser)

    def batch_by_pk(self, ModelClass, batch_size=100):
        """
        using limit/offset does a lot of table scanning to reach higher offsets
        this scanning can be slow on very large tables
        if you order by pk, you can use the pk as a pivot rather than offset
        this utilizes the index, which is faster than scanning to reach offset
        """
        qs = ModelClass.objects.order_by('pk')[:batch_size]
        while qs.exists():
            yield qs
            # qs.last() doesn't work here because we've already sliced
            # loop through so we eventually grab the last one
            for item in qs:
                start_pk = item.pk
            qs = ModelClass.objects.filter(pk__gt=start_pk).order_by('pk')[:batch_size]

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
            for models_pair in MODELS.values():
                ConfigModel, LearnerAuditModel = models_pair
                LOGGER.info(f'{LearnerAuditModel.__name__}')
                for audit_record_batch in self.batch_by_pk(LearnerAuditModel):
                    for audit_record in audit_record_batch:
                        LOGGER.info(f'{LearnerAuditModel.__name__} <{audit_record.pk}>')
                        enterprise_customer = self.find_ent_cust(audit_record.enterprise_course_enrollment_id)
                        if enterprise_customer is None:
                            continue
                        config = ConfigModel.objects.filter(enterprise_customer=enterprise_customer).first()
                        if config is None:
                            continue
                        LOGGER.info(f'{LearnerAuditModel.__name__} <{audit_record.pk}> '
                                    f'enterprise_customer_uuid={enterprise_customer.uuid}, '
                                    f'plugin_configuration_id={config.id}')
                        audit_record.enterprise_customer_uuid = enterprise_customer.uuid
                        audit_record.plugin_configuration_id = config.id
                        audit_record.save()
            for audit_record_batch in self.batch_by_pk(ContentMetadataItemTransmission):
                for audit_record in audit_record_batch:
                    LOGGER.info(f'ContentMetadataItemTransmission <{audit_record.pk}>')
                    # if we cant lookup by code, skip
                    channel_models = MODELS[audit_record.integrated_channel_code]
                    if channel_models is None:
                        continue
                    ConfigModel = channel_models[0]
                    if audit_record.enterprise_customer is None:
                        continue
                    config = ConfigModel.objects.filter(enterprise_customer=audit_record.enterprise_customer).first()
                    LOGGER.info(f'ContentMetadataItemTransmission <{audit_record.pk}> '
                                f'plugin_configuration_id={config.id}')
                    audit_record.plugin_configuration_id = config.id
                    audit_record.save()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception()

    def handle(self, *args, **options):
        """
        Backfill missing audit record foreign keys.
        """
        # Ensure that we were given an api_user name, and that User exists.
        api_username = options['api_user']
        try:
            User.objects.get(username=api_username)
        except User.DoesNotExist as no_user_error:
            raise CommandError(
                _('A user with the username {username} was not found.').format(username=api_username)
            ) from no_user_error

        self.backfill_join_keys()
