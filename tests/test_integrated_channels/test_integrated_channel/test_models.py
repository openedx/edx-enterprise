# -*- coding: utf-8 -*-
"""
Tests for the integrated channel models.
"""

import unittest

from pytest import mark

from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from test_utils import factories


@mark.django_db
class TestContentMetadataItemTransmission(unittest.TestCase):
    """
    Tests for the ``ContentMetadataItemTransmission`` model.
    """

    def setUp(self):
        super(TestContentMetadataItemTransmission, self).setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()

    def test_content_meta_data_string_representation(self):
        """
        Test the string representation of the model.
        """
        integrated_channel_code = 'test-channel-code'
        content_id = 'test-course'
        expected_string = '<Content item {content_id} for Customer {customer} with Channel {channel}>'.format(
            content_id=content_id,
            customer=self.enterprise_customer,
            channel=integrated_channel_code
        )
        transmission = ContentMetadataItemTransmission(
            enterprise_customer=self.enterprise_customer,
            integrated_channel_code=integrated_channel_code,
            content_id=content_id
        )
        assert expected_string == transmission.__repr__()
