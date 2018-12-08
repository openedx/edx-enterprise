# -*- coding: utf-8 -*-
"""
Enterprise Integrated Channel management commands.
"""

from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from django.core.management.base import CommandError
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration

# Mapping between the channel code and the channel configuration class
INTEGRATED_CHANNEL_CHOICES = OrderedDict([
    (integrated_channel_class.channel_code(), integrated_channel_class)
    for integrated_channel_class in (
        SAPSuccessFactorsEnterpriseCustomerConfiguration,
        DegreedEnterpriseCustomerConfiguration,
    )
])


class IntegratedChannelCommandMixin(object):
    """
    Contains common functionality for the IntegratedChannel management commands.
    """

    def add_arguments(self, parser):
        """
        Adds the optional arguments: ``--enterprise_customer``, ``--channel``
        """
        parser.add_argument(
            '--enterprise_customer',
            dest='enterprise_customer',
            default=None,
            metavar='ENTERPRISE_CUSTOMER_UUID',
            help=_('Transmit data for only this EnterpriseCustomer. '
                   'Omit this option to transmit to all EnterpriseCustomers with active integrated channels.'),
        )
        parser.add_argument(
            '--channel',
            dest='channel',
            default='',
            metavar='INTEGRATED_CHANNEL',
            help=_('Transmit data to this IntegrateChannel. '
                   'Omit this option to transmit to all configured, active integrated channels.'),
            choices=INTEGRATED_CHANNEL_CHOICES.keys(),
        )

    def get_integrated_channels(self, options):
        """
        Generates a list of active integrated channels for active customers, filtered from the given options.

        Raises errors when invalid options are encountered.

        See ``add_arguments`` for the accepted options.
        """
        channel_classes = self.get_channel_classes(options.get('channel'))
        filter_kwargs = {
            'active': True,
            'enterprise_customer__active': True,
        }
        enterprise_customer = self.get_enterprise_customer(options.get('enterprise_customer'))
        if enterprise_customer:
            filter_kwargs['enterprise_customer'] = enterprise_customer

        for channel_class in channel_classes:
            for integrated_channel in channel_class.objects.filter(**filter_kwargs):
                yield integrated_channel

    @staticmethod
    def get_enterprise_customer(uuid):
        """
        Returns the enterprise customer requested for the given uuid, None if not.

        Raises CommandError if uuid is invalid.
        """
        if uuid is None:
            return None
        try:
            return EnterpriseCustomer.active_customers.get(uuid=uuid)
        except EnterpriseCustomer.DoesNotExist:
            raise CommandError(
                _('Enterprise customer {uuid} not found, or not active').format(uuid=uuid))

    @staticmethod
    def get_channel_classes(channel_code):
        """
        Assemble a list of integrated channel classes to transmit to.

        If a valid channel type was provided, use it.

        Otherwise, use all the available channel types.
        """
        if channel_code:
            # Channel code is case-insensitive
            channel_code = channel_code.upper()

            if channel_code not in INTEGRATED_CHANNEL_CHOICES:
                raise CommandError(_('Invalid integrated channel: {channel}').format(channel=channel_code))

            channel_classes = [INTEGRATED_CHANNEL_CHOICES[channel_code]]
        else:
            channel_classes = INTEGRATED_CHANNEL_CHOICES.values()

        return channel_classes
