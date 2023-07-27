# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Degreed.
"""

from datetime import datetime
from logging import getLogger

from django.apps import apps

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.utils import generate_formatted_log

LOGGER = getLogger(__name__)


class Degreed2LearnerExporter(LearnerExporter):
    """
    Class to provide a Degreed learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            course_completed=False,
            **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Return a Degreed2LearnerDataTransmissionAudit with the given enrollment and course completion data.

        If no remote ID can be found, return None.
        """
        percent_grade = kwargs.get('grade_percent') * 100 if kwargs.get('grade_percent') else None
        # Degreed expects completion dates of the form 'yyyy-mm-ddTHH:MM:SS'.
        degreed_completed_timestamp = completed_date.strftime('%Y-%m-%dT%H:%M:%S') if isinstance(
            completed_date, datetime
        ) else None
        if enterprise_enrollment.enterprise_customer_user.get_remote_id(
            self.enterprise_configuration.idp_id
        ) is not None:
            Degreed2LearnerDataTransmissionAudit = apps.get_model(
                'degreed2',
                'Degreed2LearnerDataTransmissionAudit'
            )
            # We return two records here, one with the course key and one with the course run id, to account for
            # uncertainty about the type of content (course vs. course run) that was sent to the integrated channel.
            return [
                Degreed2LearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    degreed_user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                    user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                    course_id=get_course_id_for_enrollment(enterprise_enrollment),
                    completed_timestamp=completed_date,
                    degreed_completed_timestamp=degreed_completed_timestamp,
                    course_completed=course_completed,
                    grade=percent_grade,
                    enterprise_customer_uuid=enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                    plugin_configuration_id=self.enterprise_configuration.id,
                ),
                Degreed2LearnerDataTransmissionAudit(
                    enterprise_course_enrollment_id=enterprise_enrollment.id,
                    degreed_user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                    user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                    course_id=enterprise_enrollment.course_id,
                    completed_timestamp=completed_date,
                    degreed_completed_timestamp=degreed_completed_timestamp,
                    course_completed=course_completed,
                    grade=percent_grade,
                    enterprise_customer_uuid=enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                    plugin_configuration_id=self.enterprise_configuration.id,
                )
            ]
        LOGGER.info(generate_formatted_log(
            self.enterprise_configuration.channel_code(),
            enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
            enterprise_enrollment.enterprise_customer_user.user_id,
            enterprise_enrollment.course_id,
            ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
             'Degreed2 User ID not found for [{name}]'.format(
                 name=enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
             ))))
        return None
