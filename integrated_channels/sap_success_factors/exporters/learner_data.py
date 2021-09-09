# -*- coding: utf-8 -*-
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
from integrated_channels.utils import parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class SapSuccessFactorsLearnerExporter(LearnerExporter):
    """
    Class to provide a SAPSF learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            grade=None,
            course_completed=False,
            **kwargs,
    ):   # pylint: disable=arguments-differ
        """
        Return a SapSuccessFactorsLearnerDataTransmissionAudit with the given enrollment and course completion data.

        If no remote ID can be found, return None.
        """
        completed_timestamp = None
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

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
            return [
                SapSuccessFactorsLearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    sapsf_user_id=sapsf_user_id,
                    course_id=get_course_id_for_enrollment(enterprise_enrollment),
                    course_completed=course_completed,
                    completed_timestamp=completed_timestamp,
                    grade=grade,
                    total_hours=total_hours,
                    credit_hours=total_hours,
                ),
                SapSuccessFactorsLearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    sapsf_user_id=sapsf_user_id,
                    course_id=enterprise_enrollment.course_id,
                    course_completed=course_completed,
                    completed_timestamp=completed_timestamp,
                    grade=grade,
                    total_hours=total_hours,
                    credit_hours=total_hours,
                ),
            ]
        LOGGER.info(
            '[Integrated Channel] No learner data was sent for user [%s] because an SAP SuccessFactors user ID'
            ' could not be found.',
            enterprise_enrollment.enterprise_customer_user.username
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
                'Enterprise customer [%s] has no associated identity provider',
                enterprise_customer.name
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
            'Found [%d] SAP inactive learners for enterprise customer [%s]',
            total_sap_inactive_learners, enterprise_customer.name
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
                LOGGER.info(
                    'No social auth data found for inactive user with SAP student id [%s] of enterprise '
                    'customer [%s] with identity providers [%s]',
                    sap_student_id, enterprise_customer.name, ', '.join(provider.provider_id for provider in providers)
                )
                continue

            try:
                # Unlink user email from related Enterprise Customer
                EnterpriseCustomerUser.objects.unlink_user(
                    enterprise_customer=enterprise_customer,
                    user_email=social_auth_user.email,
                )
            except (EnterpriseCustomerUser.DoesNotExist, PendingEnterpriseCustomerUser.DoesNotExist):
                LOGGER.info(
                    'Learner with email [%s] and SAP student id [%s] is not linked with enterprise [%s]',
                    social_auth_user.email,
                    sap_student_id,
                    enterprise_customer.name
                )
        return None
