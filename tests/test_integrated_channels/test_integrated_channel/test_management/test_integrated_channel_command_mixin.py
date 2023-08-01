"""
Tests for the djagno management command mixin `IntegratedChannelCommandMixin`.
"""

from django.test import TestCase

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from test_utils.factories import Degreed2EnterpriseCustomerConfigurationFactory, EnterpriseCustomerFactory


class IntegratedChannelCommandMixinTests(TestCase):
    """
    Tests for the djagno management command mixin `IntegratedChannelCommandMixin`.
    """

    def setUp(self):
        self.active_customer = EnterpriseCustomerFactory.create(
            active=True,
        )
        self.inactive_customer = EnterpriseCustomerFactory.create(
            active=False,
        )
        self.active_customer_config = Degreed2EnterpriseCustomerConfigurationFactory.create(
            enterprise_customer=self.active_customer,
        )
        self.inactive_customer_config = Degreed2EnterpriseCustomerConfigurationFactory.create(
            enterprise_customer=self.inactive_customer,
        )
        self.mixin = IntegratedChannelCommandMixin()
        super().setUp()

    def test_get_integrated_channels(self):
        channels = []
        for integrated_channel in self.mixin.get_integrated_channels({}):
            channels.append(integrated_channel)
        assert self.active_customer_config in channels
        assert self.inactive_customer_config not in channels
