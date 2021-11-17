"""
Update all courses associated with canvas customer configs to show end dates
"""

from django.contrib import auth
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from integrated_channels.canvas.client import CanvasAPIClient

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin

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
        Update all past content transmission items to show end dates.
        """

        # get the edx course ids for every course in canvas
        username = options['catalog_user']
        options['prevent_disabled_configurations'] = False
        options['channel'] = 'CANVAS'

        try:
            User.objects.get(username=username)
        except User.DoesNotExist as no_user_error:
            raise CommandError('A user with the username {} was not found.'.format(username)) from no_user_error

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        # get every past transmitted course on canvas channels
        for canvas_channel in self.get_integrated_channels(options):
            transmitted_course_ids = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=canvas_channel.enterprise_customer,
                integrated_channel_code='CANVAS',
                deleted_at__isnull=True,
            ).values('content_id')

            canvas_api_client = CanvasAPIClient(canvas_channel)
            for course_id in transmitted_course_ids:
                canvas_api_client.update_participation_types(course_id['content_id'])
