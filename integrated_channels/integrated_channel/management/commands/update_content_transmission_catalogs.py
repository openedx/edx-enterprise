"""
Fetch and update all content metadata transmission audits with their respective catalog's uuid.
"""

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import update_content_transmission_catalog

User = auth.get_user_model()


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Update content transmission items to have their respective catalog's uuid.
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
        super().add_arguments(parser)

    def handle(self, *args, **options):
        """
        Update all past content transmission items to have their respective catalog's uuid.
        """
        username = options['catalog_user']
        options['prevent_disabled_configurations'] = False
        # Before we do a whole bunch of database queries, make sure that the user we were passed exists.
        try:
            User.objects.get(username=username)
        except User.DoesNotExist as no_user_error:
            raise CommandError('A user with the username {} was not found.'.format(username)) from no_user_error

        channels = self.get_integrated_channels(options)

        for channel in channels:

            channel_code = channel.channel_code()
            channel_pk = channel.pk
            update_content_transmission_catalog.delay(username, channel_code, channel_pk)
