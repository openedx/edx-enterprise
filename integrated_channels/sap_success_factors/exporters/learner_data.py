"""
Learner data exporter for Enterprise Integrated Channel SAP SuccessFactors.
"""

from logging import getLogger

from requests import RequestException

from django.apps import apps

from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from enterprise.tpa_pipeline import get_user_from_social_auth
from integrated_channels.catalog_service_utils import get_course_id_for_enrollment, get_course_run_for_enrollment
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.utils import generate_formatted_log, parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class SapSuccessFactorsLearnerExporter(LearnerExporter):
    """
    Class to provide a SAPSF learner data transmission audit prepared for serialization.
    """

    INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK = False

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            grade=None,
            content_title=None,
            progress_status=None,
            course_completed=False,
            **kwargs,
    ):   # pylint: disable=arguments-differ
        """
        Return a SapSuccessFactorsLearnerDataTransmissionAudit with the given enrollment and course completion data.

        If no remote ID can be found, return None.
        """
        sap_completed_timestamp = None
        if completed_date is not None:
            sap_completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        sapsf_user_id = enterprise_enrollment.enterprise_customer_user.get_remote_id(
            self.enterprise_configuration.idp_id
        )

        if sapsf_user_id is not None:
            SapSuccessFactorsLearnerDataTransmissionAudit = apps.get_model(
                'sap_success_factors',
                'SapSuccessFactorsLearnerDataTransmissionAudit'
            )
            # We return two records here, one with the course key and one with the course run id, to account for
            # uncertainty about the type of content (course vs. course run) that was sent to the integrated channel.
            course_run = get_course_run_for_enrollment(enterprise_enrollment)
            total_hours = 0.0
            if course_run and self.enterprise_configuration.transmit_total_hours:
                total_hours = course_run.get("estimated_hours", 0.0)
            course_id = get_course_id_for_enrollment(enterprise_enrollment)
            # We only want to send one record per enrollment and course, so we check if one exists first.
            learner_transmission_record = SapSuccessFactorsLearnerDataTransmissionAudit.objects.filter(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                course_id=course_id,
            ).first()
            if learner_transmission_record is None:
                learner_transmission_record = SapSuccessFactorsLearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    sapsf_user_id=sapsf_user_id,
                    user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                    course_id=get_course_id_for_enrollment(enterprise_enrollment),
                    course_completed=course_completed,
                    completed_timestamp=completed_date,
                    sap_completed_timestamp=sap_completed_timestamp,
                    grade=grade,
                    content_title=content_title,
                    progress_status=progress_status,
                    total_hours=total_hours,
                    credit_hours=total_hours,
                    enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                    plugin_configuration_id=self.enterprise_configuration.id
                )
            return [learner_transmission_record]
        LOGGER.info(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                enterprise_enrollment.enterprise_customer_user.user_id,
                enterprise_enrollment.course_id,
                '[Integrated Channel] No learner data was sent for user '
                f'{enterprise_enrollment.enterprise_customer_user.username} because an SAP SuccessFactors user ID '
                ' could not be found.'
            )
        )
        return None


class SapSuccessFactorsLearnerManger:
    """
    Class to manage SAPSF learners data and their relation with enterprise.
    """

    def __init__(self, enterprise_configuration, client=SAPSuccessFactorsAPIClient):
        """
        Use the ``SAPSuccessFactorsAPIClient`` for content metadata transmission to SAPSF.

        Arguments:
            enterprise_configuration (required): SAPSF configuration connecting an enterprise to an integrated channel.
            client: The REST API client that will fetch data from integrated channel.
        """
        self.enterprise_configuration = enterprise_configuration
        self.client = client(enterprise_configuration) if client else None

    def _get_inactive_learners(self):
        """ Gets inactive learners list from the client or raises ClientError on failure. """
        try:
            sap_inactive_learners = self.client.get_inactive_sap_learners()
        except RequestException as exc:
            raise ClientError(
                'SAPSuccessFactorsAPIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc
        return sap_inactive_learners

    def _get_identity_providers(self):
        """ Logic check for getting an identity provider preflight validation, split out for unit testing."""
        enterprise_customer = self.enterprise_configuration.enterprise_customer
        providers = enterprise_customer.identity_providers
        if not enterprise_customer.has_identity_providers:
            LOGGER.info(
                generate_formatted_log(
                    self.enterprise_configuration.channel_code(),
                    self.enterprise_configuration.enterprise_customer.uuid,
                    None,
                    None,
                    f'Enterprise customer {enterprise_customer.name} has no associated identity provider'
                )
            )
            return None
        return providers

    def unlink_learners(self):
        """
        Iterate over each learner and unlink inactive SAP channel learners.

        This method iterates over each enterprise learner and unlink learner
        from the enterprise if the learner is marked inactive in the related
        integrated channel.
        """
        sap_inactive_learners = self._get_inactive_learners()

        total_sap_inactive_learners = len(sap_inactive_learners) if sap_inactive_learners else 0
        enterprise_customer = self.enterprise_configuration.enterprise_customer
        LOGGER.info(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                f'Found {total_sap_inactive_learners} SAP inactive learners for '
                f'enterprise customer {enterprise_customer.name}'
            )
        )
        if not sap_inactive_learners:
            return None

        providers = self._get_identity_providers()
        if not providers:
            return None

        for sap_inactive_learner in sap_inactive_learners:
            sap_student_id = sap_inactive_learner['studentID']
            social_auth_user = get_user_from_social_auth(providers, sap_student_id, enterprise_customer)
            if not social_auth_user:
                continue

            try:
                # Unlink user email from related Enterprise Customer
                EnterpriseCustomerUser.objects.unlink_user(
                    enterprise_customer=enterprise_customer,
                    user_email=social_auth_user.email,
                )
            except (EnterpriseCustomerUser.DoesNotExist, PendingEnterpriseCustomerUser.DoesNotExist):
                LOGGER.info(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'Learner with email {social_auth_user.email} and SAP student id {sap_student_id} '
                        f'is not linked with enterprise {enterprise_customer.name}'
                    )
                )
        return None
