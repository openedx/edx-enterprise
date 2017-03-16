"""
Module tests classes responsible for transmitting data to integrated channels.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import mock

from integrated_channels.sap_success_factors.transmitters import courses, learner_data


class TestSuccessFactorsCourseTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsCourseTransmitter.
    """

    def test_init(self):
        config = mock.MagicMock()
        transmitter = courses.SuccessFactorsCourseTransmitter(config)
        assert transmitter.__class__.__bases__[0].__name__ == 'SuccessFactorsTransmitterBase'
        assert transmitter.configuration is config


class TestSuccessFactorsLearnerDataTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsLearnerDataTransmitter.
    """

    def test_init(self):
        config = mock.MagicMock()
        transmitter = learner_data.SuccessFactorsLearnerDataTransmitter(config)
        assert transmitter.__class__.__bases__[0].__name__ == 'SuccessFactorsTransmitterBase'
        assert transmitter.configuration is config
