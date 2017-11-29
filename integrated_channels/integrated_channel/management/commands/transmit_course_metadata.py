# -*- coding: utf-8 -*-
"""
Transmits information about an enterprise's course catalog to connected IntegratedChannels
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import transmit_course_metadata

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

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
            transmit_course_metadata.delay(username, channel_code, channel_pk)
