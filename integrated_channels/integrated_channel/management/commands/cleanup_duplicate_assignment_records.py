"""
Remove duplicate transmitted assignments for the integrated channels.
"""

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import cleanup_duplicate_assignment_records

User = auth.get_user_model()


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Management command which removes duplicated assignment records transmitted to the IntegratedChannel(s) configured
    for the given EnterpriseCustomer.

    Collect the enterprise enrollments with data sharing consent, and ensure deduping of assignments  for each unique
    course that has previously been transmitted.

    Note: this management command is currently only configured to work with only the Canvas integrated channel.
    """
    help = _('''
    Verify and remove any duplicated assignments transmitted to the IntegratedChannel(s) configured for the given
     EnterpriseCustomer.
    ''')

    def add_arguments(self, parser):
        """
        Add required --api_user argument to the parsetest_learner_data_multiple_coursesr.
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
        De-duplicate assignments transmitted for the EnterpriseCustomer(s)
        """
        # Ensure that we were given an api_user name, and that User exists.
        api_username = options['api_user']

        # For now we only need/want this command to run with Canvas
        options['channel'] = 'CANVAS'
        try:
            User.objects.get(username=api_username)
        except User.DoesNotExist as no_user_error:
            raise CommandError(
                _('A user with the username {username} was not found.').format(username=api_username)
            ) from no_user_error

        for canvas_channel in self.get_integrated_channels(options):
            cleanup_duplicate_assignment_records.delay(api_username, canvas_channel.channel_code(), canvas_channel.pk)
