"""
Enterprise Integrated Channel management commands.
"""
from __future__ import absolute_import, unicode_literals

from django.core.management.base import CommandError
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration


# Import djcelery, or stub it if not available.
try:
    from djcelery.celery import task as celery_task
except ImportError:
    def celery_task(func):
        """Use a no-op decorator if djcelery is not available."""
        def no_delay(*args, **kwargs):
            """
            Provides the celery.task.delay function, which can be used to spawn an asynchronous celery task.
            Here, it just calls the function.
            """
            func(*args, **kwargs)
        func.delay = no_delay
        return func

# Mapping between the channel code and the channel configuration class
INTEGRATED_CHANNEL_CHOICES = {
    channel_class.channel_code(): channel_class
    for channel_class in (SAPSuccessFactorsEnterpriseCustomerConfiguration, )
}


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
            metavar=_('ENTERPRISE_CUSTOMER_UUID'),
            help=_('Transmit data for only this EnterpriseCustomer. '
                   'Omit this option to transmit to all EnterpriseCustomers with active integrated channels.'),
        )
        parser.add_argument(
            '--channel',
            dest='channel',
            default='',
            metavar=_('INTEGRATED_CHANNEL'),
            help=_('Transmit data to this IntegrateChannel. '
                   'Omit this option to transmit to all configured, active integrated channels.'),
            choices=INTEGRATED_CHANNEL_CHOICES.keys(),
        )

    def get_integrated_channels(self, options, **filter_kwargs):
        """
        Generates a list of active integrated channels, filtered from the given options.

        Raises errors when invalid options are encountered.

        See ``add_arguments`` for the accepted options.

        filter_kwargs is passed as an additional set of parameters that jobs can use to restrict
        the database query used to retrieve relevant integrated channels.
        """
        # If a valid enterprise customer uuid was provided, transmit for that customer.
        # Otherwise, transmit for all customers.
        enterprise_customer = None
        enterprise_customer_uuid = options['enterprise_customer']
        if enterprise_customer_uuid:
            try:
                enterprise_customer = EnterpriseCustomer.active_customers.get(uuid=enterprise_customer_uuid)
            except EnterpriseCustomer.DoesNotExist:
                raise CommandError(
                    _('Enterprise customer {uuid} not found, or not active').format(uuid=enterprise_customer_uuid))

        # Assemble a list of integrated channel classes to transmit to.
        # If a valid channel type was provided, use it.
        # Otherwise, use all the available channel types.
        channel_code = options['channel'].upper()
        if channel_code:
            if channel_code not in INTEGRATED_CHANNEL_CHOICES:
                raise CommandError(_('Invalid integrated channel: {channel}').format(channel=channel_code))

            channel_classes = [INTEGRATED_CHANNEL_CHOICES[channel_code]]
        else:
            channel_classes = INTEGRATED_CHANNEL_CHOICES.values()

        # Loop through each channel class (optionally for a specific enterprise customer)
        for channel_class in channel_classes:
            # Use Active channels only
            integrated_channels = channel_class.objects.filter(active=True)

            if enterprise_customer:
                integrated_channels = integrated_channels.filter(enterprise_customer=enterprise_customer)

            # Filter down to the integrated channels that are strictly relevant
            if filter_kwargs:
                integrated_channels = integrated_channels.filter(**filter_kwargs)

            # Gen the learner data to each integrated channel
            for integrated_channel in integrated_channels:
                yield integrated_channel
