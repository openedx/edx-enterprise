"""
Update all courses associated with canvas customer configs to show end dates
"""

from django.apps import apps
from django.contrib import auth
from django.core.management.base import BaseCommand

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin

User = auth.get_user_model()


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Update content transmission items to have their respective catalog's uuid.

    ./manage.py lms backfill_course_end_dates
    """
    def handle(self, *args, **options):
        """
        Update all past content transmission items to show end dates.
        """
        options['prevent_disabled_configurations'] = False
        options['channel'] = 'CANVAS'

        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )

        # get every past transmitted course on canvas channels
        for canvas_channel in self.get_integrated_channels(options):
            transmitted_course_ids = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=canvas_channel.enterprise_customer,
                integrated_channel_code='CANVAS',
                remote_deleted_at__isnull=True,
            ).values('content_id')

            CanvasAPIClient(canvas_channel).update_participation_types(transmitted_course_ids)
