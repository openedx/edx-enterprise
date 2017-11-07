# -*- coding: utf-8 -*-
"""
Tests for the base transmitter.
"""

from __future__ import absolute_import, unicode_literals

import unittest

from integrated_channels.integrated_channel.transmitters import Transmitter


class TestTransmitter(unittest.TestCase):
    """
    Tests for the base ``Transmitter`` class.
    """

    def test_transmit(self):
        """
        The ``transmit`` method is not implemented at the base, and so should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            Transmitter(enterprise_configuration=None).transmit('fake-payload')
