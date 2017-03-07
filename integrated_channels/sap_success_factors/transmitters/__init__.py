"""
Package for transmitting data to SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

from abc import ABCMeta, abstractmethod
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient


class SuccessFactorsTransmitterBase:  # pylint: disable=metaclass-assignment
    """
    Base class for transmitting data to SuccessFactors.
    """
    __metaclass__ = ABCMeta

    def __init__(self, enterprise_configuration):
        """
        The base init function that initializes a SAPSuccessFactorsAPIClient for subsequent calls.

        Args:
            enterprise_configuration (SAPSuccessFactorsEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with SAP SuccessFactors
        """
        self.enterprise_configuration = enterprise_configuration
        self.client = SAPSuccessFactorsAPIClient(enterprise_configuration)

    @abstractmethod
    def transmit(self, payload):
        """
        The abstract method for making particular calls to SAP SuccessFactors, implemented by each child class.
        """
