# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.blackboard.
"""

import unittest
import pytest

from test_utils.factories import BlackboardEnterpriseCustomerConfigurationFactory
from integrated_channels.blackboard.client import BlackboardAPIClient


@pytest.mark.django_db
class TestBlackboardApiClient(unittest.TestCase):
    """
    Test Blackboard API client methods.
    """

    def setUp(self):
        super(TestBlackboardApiClient, self).setUp()
        self.enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            client_id="id",
            client_secret="secret",
            blackboard_base_url="https://base.url",
            refresh_token="token",
        )

    def test_client_has_valid_app_config(self):
        api_client = BlackboardAPIClient(self.enterprise_config)
        assert api_client.config is not None
