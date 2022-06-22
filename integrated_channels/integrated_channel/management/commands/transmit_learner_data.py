"""
Transmits consenting enterprise learner data to the integrated channels.
"""

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import transmit_learner_data

User = auth.get_user_model()


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
    stealth_options = ('enterprise_customer_slug', 'user1', 'user2')

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
        super().add_arguments(parser)

    def handle(self, *args, **options):
        """
        Transmit the learner data for the EnterpriseCustomer(s) to the active integration channels.
        """
        # Ensure that we were given an api_user name, and that User exists.
        api_username = options['api_user']
        try:
            User.objects.get(username=api_username)
        except User.DoesNotExist as no_user_error:
            raise CommandError(
                _('A user with the username {username} was not found.').format(username=api_username)
            ) from no_user_error

        # Transmit the learner data to each integrated channel
        for integrated_channel in self.get_integrated_channels(options):
            # NOTE pass arguments as named kwargs for use in lock key
            transmit_learner_data.delay(
                username=api_username, channel_code=integrated_channel.channel_code(), channel_pk=integrated_channel.pk)
