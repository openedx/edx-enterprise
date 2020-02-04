# -*- coding: utf-8 -*-
"""
Package for generic data transmitters which send serialized data to integrated channels.
"""

from __future__ import absolute_import, unicode_literals


class Transmitter:
    """
    Interface for transmitting data to an integrated channel.

    The interface contains the following method(s):

    transmit(payload)
        payload - The ``Exporter`` object expected to implement an ``export`` method that returns serialized data.
    """

    def __init__(self, enterprise_configuration, client=None):
        """
        Prepares a configuration and a client to be used to transmit data to an integrated channel.

        Arguments:
            * enterprise_configuration - The configuration connecting an enterprise to an integrated channel.
            * client - The REST API client that'll transmit serialized data.
        """
        self.enterprise_configuration = enterprise_configuration
        self.client = client(enterprise_configuration) if client else None

    def transmit(self, payload, **kwargs):
        """
        The abstract interface method for sending exported data to an integrated channel through its API client.
        """
        raise NotImplementedError('Implement in concrete subclass transmitter.')
