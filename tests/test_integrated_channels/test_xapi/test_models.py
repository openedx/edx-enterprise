# -*- coding: utf-8 -*-
"""
Tests for the xAPI models.
"""

from __future__ import absolute_import, unicode_literals

import base64
import unittest

from pytest import mark

from test_utils import factories


@mark.django_db
class TestXAPILRSConfiguration(unittest.TestCase):
    """
    Tests for the ``XAPILRSConfiguration`` model.
    """

    def setUp(self):
        super(TestXAPILRSConfiguration, self).setUp()
        self.x_api_lrs_config = factories.XAPILRSConfigurationFactory()

    def test_string_representation(self):
        """
        Test the string representation of the model.
        """
        expected_string = '<XAPILRSConfiguration for Enterprise {enterprise_name}>'.format(
            enterprise_name=self.x_api_lrs_config.enterprise_customer.name,
        )
        assert expected_string == self.x_api_lrs_config.__repr__()

    def test_authorization_header(self):
        """
        Test the authorization header for the configuration.
        """
        expected_header = 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(
                key=self.x_api_lrs_config.key,
                secret=self.x_api_lrs_config.secret
            ).encode()).decode()
        )
        assert expected_header == self.x_api_lrs_config.authorization_header
