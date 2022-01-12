"""
Class for transmitting learner data to SuccessFactors.
"""

import logging

from enterprise.models import EnterpriseCustomerUser
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)


class SapSuccessFactorsLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to SuccessFactors.
    """

    INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK = False

    def __init__(self, enterprise_configuration, client=SAPSuccessFactorsAPIClient):
        """
        By default, use the ``SAPSuccessFactorsAPIClient`` for learner data transmission to SAPSF.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to SAP SuccessFactors using the client.

        Args:
            payload: The learner data exporter for SAP SuccessFactors
        """
        kwargs['app_label'] = 'sap_success_factors'
        kwargs['model_name'] = 'SapSuccessFactorsLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'sapsf_user_id'
        super().transmit(payload, **kwargs)

    def handle_transmission_error(self, learner_data, client_exception):
        """Handle the case where the employee on SAPSF's side is marked as inactive."""
        try:
            sys_msg = str(client_exception.message)
            ecu = EnterpriseCustomerUser.objects.get(
                enterprise_enrollments__id=learner_data.enterprise_course_enrollment_id)

        except AttributeError:
            pass
        else:
            if sys_msg and 'user account is inactive' in sys_msg:
                ecu.active = False
                ecu.save()
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        ecu.enterprise_customer.uuid,
                        ecu.user_id,
                        None,
                        f'User with LMS ID {ecu.user_id}, ECU ID {ecu.id} is a '
                        f'former employee of {ecu.enterprise_customer} '
                        'and has been marked inactive in SAPSF. Now marking inactive internally.'
                    )
                )
                return
