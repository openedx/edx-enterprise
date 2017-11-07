# -*- coding: utf-8 -*-
"""
Class for transmitting course metadata to SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.integrated_channel.transmitters.course_metadata import CourseTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient


class SapSuccessFactorsCourseTransmitter(CourseTransmitter):
    """
    This transmitter transmits a course metadata export to SAPSF.
    """

    def __init__(self, enterprise_configuration, client=SAPSuccessFactorsAPIClient):
        """
        By default, use the ``SAPSuccessFactorsAPIClient`` for course metadata transmission to SAPSF.
        """
        super(SapSuccessFactorsCourseTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
