"""
Class for transmitting learner data to SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals
import logging
from integrated_channels.sap_success_factors.transmitters import SuccessFactorsTransmitterBase


LOGGER = logging.getLogger(__name__)


class SuccessFactorsLearnerDataTransmitter(SuccessFactorsTransmitterBase):
    """
    This endpoint is intended to receive data routed from the enterprise app that is ready to be sent to
    SuccessFactors. Requests should include most of the data that we need to send to SuccessFactors, so that
    only basic validation that needs to be performed on the data, minimizing lookups.

    Implementation will look something like:

    Perform basic validation on the input (how much will probably depend on if this becomes a separate endpoint,
     or only accessible from the router.)

    Retrieve oauth access token from SuccessFactors, based on OCNWebServicesEnterpriseCustomerConfiguration.
    This can either initiate generating a new token, or using an unexpired token which we have cached.

    Fetch the remaining learner data we need to send to SuccessFactors. This includes:
        The SuccessFactors user id which should be available from when the user was first authenticated via SSO.

    Transform the data into the format expected by SuccessFactors.

    Send the transformed learner data to SuccessFactors using the configured endpoint
    (taken from OCNWebServicesConfiguration and OCNWebServicesEnterpriseCustomerConfiguration) and the oauth token.

    Record information about the success/failure of posting the learner data to SuccessFactors in
    the LearnerDataTransmissionAudit object provided, and save it to the database.

    """
    def transmit(self, learner_data):
        """
        Transmit the learner data payload to the SAP SuccessFactors channel.
        """
        # TODO ENT-221 will handle transmitting the learner data payload to the channel
        # We only want to transmit if learner_data.course_completed == True.
        LOGGER.info(learner_data.serialize())
