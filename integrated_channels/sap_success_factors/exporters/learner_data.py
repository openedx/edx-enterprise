# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel SAP SuccessFactors.
"""


from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.apps import apps

from enterprise.utils import parse_course_key
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
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
