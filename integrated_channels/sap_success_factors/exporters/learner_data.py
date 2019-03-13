# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel SAP SuccessFactors.
"""


from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.apps import apps

from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from enterprise.tpa_pipeline import get_user_from_social_auth
from enterprise.utils import get_identity_provider, parse_course_key
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.utils import parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class SapSuccessFactorsLearnerExporter(LearnerExporter):
    """
    Class to provide a SAPSF learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(self, enterprise_enrollment, completed_date=None, grade=None, is_passing=False):
        """
        Return a SapSuccessFactorsLearnerDataTransmissionAudit with the given enrollment and course completion data.

        If completed_date is None and the learner isn't passing, then course completion has not been met.

        If no remote ID can be found, return None.
        """
        completed_timestamp = None
        course_completed = False
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)
            course_completed = is_passing

        sapsf_user_id = enterprise_enrollment.enterprise_customer_user.get_remote_id()

        if sapsf_user_id is not None:
            SapSuccessFactorsLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
                'sap_success_factors',
                'SapSuccessFactorsLearnerDataTransmissionAudit'
            )
            # We return two records here, one with the course key and one with the course run id, to account for
            # uncertainty about the type of content (course vs. course run) that was sent to the integrated channel.
            return [
                SapSuccessFactorsLearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    sapsf_user_id=sapsf_user_id,
                    course_id=parse_course_key(enterprise_enrollment.course_id),
                    course_completed=course_completed,
                    completed_timestamp=completed_timestamp,
                    grade=grade,
                ),
                SapSuccessFactorsLearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    sapsf_user_id=sapsf_user_id,
                    course_id=enterprise_enrollment.course_id,
                    course_completed=course_completed,
                    completed_timestamp=completed_timestamp,
                    grade=grade,
                ),
            ]
        else:
            LOGGER.debug(
                'No learner data was sent for user [%s] because an SAP SuccessFactors user ID could not be found.',
                enterprise_enrollment.enterprise_customer_user.username
            )


class SapSuccessFactorsLearnerManger(object):
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

    def unlink_learners(self):
        """
        Iterate over each learner and unlink inactive SAP channel learners.

        This method iterates over each enterprise learner and unlink learner
        from the enterprise if the learner is marked inactive in the related
        integrated channel.
        """
        sap_inactive_learners = self.client.get_inactive_sap_learners()
        enterprise_customer = self.enterprise_configuration.enterprise_customer
        if not sap_inactive_learners:
            LOGGER.info(
                'Enterprise customer {%s} has no SAPSF inactive learners',
                enterprise_customer.name
            )
            return

        provider_id = enterprise_customer.identity_provider
        tpa_provider = get_identity_provider(provider_id)
        if not tpa_provider:
            LOGGER.info(
                'Enterprise customer {%s} has no associated identity provider',
                enterprise_customer.name
            )
            return None

        for sap_inactive_learner in sap_inactive_learners:
            social_auth_user = get_user_from_social_auth(tpa_provider, sap_inactive_learner['studentID'])
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
                    'Learner with email {%s} is not associated with Enterprise Customer {%s}',
                    social_auth_user.email,
                    enterprise_customer.name
                )
