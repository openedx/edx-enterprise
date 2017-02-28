"""
Module tests classes responsible for transmitting data to integrated channels.
"""
from __future__ import absolute_import, unicode_literals

import unittest

from integrated_channels.sap_success_factors.transmitters import courses, learner_data


class TestSuccessFactorsCourseTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsCourseTransmitter.
    """

    def test_init(self):
        transmitter = courses.SuccessFactorsCourseTransmitter()
        assert transmitter.__class__.__bases__[0].__name__ == 'SuccessFactorsTransmitterBase'


class TestSuccessFactorsLearnerDataTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsLearnerDataTransmitter.
    """

    def test_init(self):
        transmitter = learner_data.SuccessFactorsLearnerDataTransmitter()
        assert transmitter.__class__.__bases__[0].__name__ == 'SuccessFactorsTransmitterBase'
