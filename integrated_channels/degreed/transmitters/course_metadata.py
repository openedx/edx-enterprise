# -*- coding: utf-8 -*-
"""
Class for transmitting course metadata to Degreed.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.degreed.client import DegreedAPIClient
from integrated_channels.integrated_channel.transmitters.course_metadata import CourseTransmitter


class DegreedCourseTransmitter(CourseTransmitter):
    """
    This transmitter transmits a course metadata export to Degreed.
    """

    def __init__(self, enterprise_configuration, client=DegreedAPIClient):
        """
        By default, use the ``DegreedAPIClient`` for course metadata transmission to Degreed.
        """
        super(DegreedCourseTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
