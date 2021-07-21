# -*- coding: utf-8 -*-
"""
Enterprise Integrated Channel management commands.
"""

from collections import OrderedDict

from django.core.management.base import CommandError
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration

# Mapping between the channel code and the channel configuration class
INTEGRATED_CHANNEL_CHOICES = OrderedDict([
    (integrated_channel_class.channel_code(), integrated_channel_class)
    for integrated_channel_class in (
        BlackboardEnterpriseCustomerConfiguration,
        CanvasEnterpriseCustomerConfiguration,
        CornerstoneEnterpriseCustomerConfiguration,
        DegreedEnterpriseCustomerConfiguration,
        MoodleEnterpriseCustomerConfiguration,
        SAPSuccessFactorsEnterpriseCustomerConfiguration,
    )
])

ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES = OrderedDict([
    (integrated_channel_class.channel_code(), integrated_channel_class)
    for integrated_channel_class in (
        BlackboardEnterpriseCustomerConfiguration,
        CanvasEnterpriseCustomerConfiguration,
    )
])

# Since Cornerstone is following pull content model we don't need to include CSOD customers in a content metadata
# transmission job
CONTENT_METADATA_JOB_INTEGRATED_CHANNEL_CHOICES = OrderedDict([
    (integrated_channel_class.channel_code(), integrated_channel_class)
    for integrated_channel_class in (
        BlackboardEnterpriseCustomerConfiguration,
        CanvasEnterpriseCustomerConfiguration,
        DegreedEnterpriseCustomerConfiguration,
        MoodleEnterpriseCustomerConfiguration,
        SAPSuccessFactorsEnterpriseCustomerConfiguration,
    )
])


class IntegratedChannelCommandMixin:
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
            choices=list(INTEGRATED_CHANNEL_CHOICES.keys()),
        )

    def get_integrated_channels(self, options):
        """
        Generates a list of active integrated channels for active customers, filtered from the given options.

        Raises errors when invalid options are encountered.

        See ``add_arguments`` for the accepted options.
        """
        assessment_level_support = options.get('assessment_level_support', False)
        content_metadata_job_support = options.get('content_metadata_job_support', False)
        channel_classes = self.get_channel_classes(
            options.get('channel'),
            assessment_level_support=assessment_level_support,
            content_metadata_job_support=content_metadata_job_support,
        )
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
        except EnterpriseCustomer.DoesNotExist as no_customer_exception:
            raise CommandError(
                _('Enterprise customer {uuid} not found, or not active').format(uuid=uuid)
            ) from no_customer_exception

    @staticmethod
    def get_channel_classes(channel_code, assessment_level_support=False, content_metadata_job_support=False):
        """
        Assemble a list of integrated channel classes to transmit to.

        If a valid channel type was provided, use it.

        Otherwise, use all the available channel types.
        """
        if assessment_level_support:
            channel_choices = ASSESSMENT_LEVEL_REPORTING_INTEGRATED_CHANNEL_CHOICES
        elif content_metadata_job_support:
            channel_choices = CONTENT_METADATA_JOB_INTEGRATED_CHANNEL_CHOICES
        else:
            channel_choices = INTEGRATED_CHANNEL_CHOICES

        if channel_code:
            # Channel code is case-insensitive
            channel_code = channel_code.upper()

            if channel_code not in channel_choices:
                raise CommandError(_('Invalid integrated channel: {channel}').format(channel=channel_code))

            channel_classes = [channel_choices[channel_code]]
        else:
            channel_classes = list(channel_choices.values())

        return channel_classes


class IntegratedChannelCommandUtils(IntegratedChannelCommandMixin):
    """
    This is a wrapper class to avoid using mixin in methods
    """
