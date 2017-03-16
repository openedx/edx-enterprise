"""
Package for transmitting data to SuccessFactors.
"""
from __future__ import unicode_literals


class SuccessFactorsTransmitterBase(object):
    """
    Base class for transmitting data to SuccessFactors.
    """
    def __init__(self, sap_configuration):
        self.configuration = sap_configuration
        super(SuccessFactorsTransmitterBase, self).__init__()
