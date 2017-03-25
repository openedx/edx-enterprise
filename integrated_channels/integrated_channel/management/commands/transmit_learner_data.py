"""
Transmits consenting enterprise learner data to the integrated channels.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from . import IntegratedChannelCommandMixin, celery_task, INTEGRATED_CHANNEL_CHOICES


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Management command which transmits learner course completion data to the IntegratedChannel(s) configured for the
    given EnterpriseCustomer.

    Collect the enterprise learner data for enrollments with data sharing consent, and transmit each to the
    EnterpriseCustomer's configured IntegratedChannel(s).
    """
    help = _('''
    Transmit Enterprise learner course completion data for the given EnterpriseCustomer.
    ''')

    def add_arguments(self, parser):
        """
        Add required --api_user argument to the parser.
        """
        parser.add_argument(
            '--api_user',
            dest='api_user',
            required=True,
            metavar='LMS_API_USERNAME',
            help=_('Username of a user authorized to fetch grades from the LMS API.'),
        )
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        """
        Transmit the learner data for the EnterpriseCustomer(s) to the active integration channels.
        """
        # Ensure that we were given an api_user name, and that User exists.
        api_username = options['api_user']
        try:
            User.objects.get(username=api_username)
        except User.DoesNotExist:
            raise CommandError(_('A user with the username {username} was not found.').format(username=api_username))

        # Transmit the learner data to each integrated channel
        for integrated_channel in self.get_integrated_channels(options):
            self.transmit_learner_data.delay(api_username, integrated_channel.channel_code(), integrated_channel.pk)

    @staticmethod
    @celery_task
    def transmit_learner_data(username, channel_code, channel_pk):
        """
        Allows each enterprise customer's integrated channel to collect and transmit data within its own celery task.
        """
        api_user = User.objects.get(username=username)
        integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
        integrated_channel.transmit_learner_data(api_user)
