"""
Class for transmitting course data to SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

import logging

from integrated_channels.sap_success_factors.transmitters import SuccessFactorsTransmitterBase


LOGGER = logging.getLogger(__name__)


class SuccessFactorsCourseTransmitter(SuccessFactorsTransmitterBase):
    """
    This endpoint is intended to carry out an export of course data to SuccessFactors for a given Enterprise.

    Implementation will look something like:

    Perform basic validation on the input (e.g. is this Enterprise configured for SuccessFactors?)

    Retrieve oauth access token from SuccessFactors, based on OCNWebServicesEnterpriseCustomerConfiguration.
    This can either initiate generating a new token, or using an unexpired token which we have cached.

    Find which catalog is associated with the enterprise customer.

    Retrieve course data in the catalog from the Catalog API.

    Transform course data into the format expected by SuccessFactors.

    Send the transformed course data to SuccessFactors using the configured endpoint
    (taken from OCNWebServicesConfiguration and OCNWebServicesEnterpriseCustomerConfiguration) and the oauth token.

    Record information about the success/failure of posting the course data to SuccessFactors in
     CourseContentExportAudit.
    """
    def transmit(self, courseware_exporter):
        """
        Get serialized data from the courseware exporter and transmit it.
        """
        LOGGER.info(courseware_exporter.get_serialized_data())
