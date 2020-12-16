"""
Tests for the Blackboard content metadata transmitter.
"""

import unittest

from pytest import mark

from integrated_channels.blackboard.transmitters.content_metadata import BlackboardContentMetadataTransmitter
from test_utils.factories import BlackboardEnterpriseCustomerConfigurationFactory


@mark.django_db
class TestBlackboardContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``BlackboardContentMetadataTransmitter``.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory()

    def test_prepare_items_for_transmission(self):
        transmitter = BlackboardContentMetadataTransmitter(self.enterprise_config)
        channel_metadata_items = [{'field': 'value'}]
        expected_items = channel_metadata_items[0]

        # pylint: disable=protected-access
        assert transmitter._prepare_items_for_transmission(
            channel_metadata_items
        ) == expected_items
