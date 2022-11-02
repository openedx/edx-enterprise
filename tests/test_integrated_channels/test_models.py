"""
Test suite surrounding the database models for Enterprise Integrated Channels.
"""

import unittest

import ddt
from pytest import mark

from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestIntegratedChannelsModels(unittest.TestCase):
    """
    Test suite for Integrated Channels models
    """
    def setUp(self):
        self.blackboard_config = factories.BlackboardEnterpriseCustomerConfigurationFactory()
        self.canvas_config = factories.CanvasEnterpriseCustomerConfigurationFactory()
        self.cornerstone_config = factories.CornerstoneEnterpriseCustomerConfigurationFactory()
        self.degreed_config = factories.DegreedEnterpriseCustomerConfigurationFactory()
        self.degreed2_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        self.moodle_config = factories.MoodleEnterpriseCustomerConfigurationFactory()
        self.sap_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory()
        super().setUp()

    @ddt.data(
        BlackboardEnterpriseCustomerConfiguration,
        CanvasEnterpriseCustomerConfiguration,
        CornerstoneEnterpriseCustomerConfiguration,
        DegreedEnterpriseCustomerConfiguration,
        Degreed2EnterpriseCustomerConfiguration,
        MoodleEnterpriseCustomerConfiguration,
        SAPSuccessFactorsEnterpriseCustomerConfiguration,
    )
    def test_integration_customer_config_soft_delete(self, channel_config):
        """
        Test that the all integration customer configs support soft delete
        """
        # Assert we have something to work with
        assert len(channel_config.objects.all()) == 1

        # Soft delete
        existing_config = channel_config.objects.first()
        existing_config.delete()
        assert not channel_config.objects.all()

        # Assert record not actually deleted
        assert len(channel_config.all_objects.all()) == 1
        assert channel_config.all_objects.first().deleted_at

        # Resurrect the record
        channel_config.all_objects.first().revive()
        assert len(channel_config.objects.all()) == 1
        assert not channel_config.objects.first().deleted_at

        # Hard delete the record
        channel_config.objects.first().hard_delete()
        assert not channel_config.objects.all()
        assert not channel_config.all_objects.all()
