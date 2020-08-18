"""
Tests for the Canvas content metadata transmitter.
"""

import unittest
from pytest import mark

from test_utils import factories
from test_utils.factories import (
    CanvasEnterpriseCustomerConfigurationFactory,
)
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataItemExport
from integrated_channels.canvas.transmitters.content_metadata import CanvasContentMetadataTransmitter


@mark.django_db
class TestCanvasContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``CanvasContentMetadataTransmitter``.
    """

    def setUp(self):
        super(TestCanvasContentMetadataTransmitter, self).setUp()
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Quokka Search Party')
        self.enterprise_config = CanvasEnterpriseCustomerConfigurationFactory()

    def test_prepare_items_for_transmission(self):
        transmitter = CanvasContentMetadataTransmitter(self.enterprise_config)
        channel_metadata_items =[ {'field': 'value'} ]
        expected_items = {
            'course': channel_metadata_items[0],
        }
        assert transmitter._prepare_items_for_transmission(channel_metadata_items) == expected_items
