"""
Transmits information about an enterprise's course catalog to connected IntegratedChannels
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.utils import SapCourseExporter

from . import INTEGRATED_CHANNEL_CHOICES, IntegratedChannelCommandMixin, celery_task


PLUGIN_MAPPING = {
    SAPSuccessFactorsEnterpriseCustomerConfiguration: SapCourseExporter,
}

LOGGER = getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Transmit courseware data to the IntegratedChannel(s) linked to any or all EnterpriseCustomers.
    """

    def add_arguments(self, parser):
        """
        Add required arguments to the parser.
        """
        parser.add_argument(
            '--catalog_user',
            dest='catalog_user',
            required=True,
            metavar='ENTERPRISE_CATALOG_API_USERNAME',
            help='Use this user to access the Course Catalog API.'
        )
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        """
        Transmit the courseware data for the EnterpriseCustomer(s) to the active integration channels.
        """
        username = options['catalog_user']

        # Before we do a whole bunch of database queries, make sure that the user we were passed exists.
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError('A user with the username {} was not found.'.format(username))

        channels = self.get_integrated_channels(options, enterprise_customer__catalog__isnull=False)

        for channel in channels:
            channel_code = channel.channel_code()
            channel_pk = channel.pk
            send_data_task.delay(username, channel_code, channel_pk)


@celery_task
def send_data_task(username, channel_code, channel_pk):
    """
    Task to send course data to each linked integrated channel

    Args:
        user: The user whose access token to use for course discovery API access
        enterprise_customer: The EnterpriseCustomer whose integrated channels we need to send.
    """
    user = User.objects.get(username=username)
    channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)

    LOGGER.info(
        'Processing courses for integrated channel using configuration: %s',
        channel,
    )

    channel.transmit_course_data(user)
