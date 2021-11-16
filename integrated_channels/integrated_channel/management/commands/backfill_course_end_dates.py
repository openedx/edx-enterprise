"""
Update all courses associated with canvas customer configs to show end dates
"""

from integrated_channels.canvas.client import CanvasAPIClient
from django.contrib import auth
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin

User = auth.get_user_model()

class Command(IntegratedChannelCommandMixin, BaseCommand):
    # """
    # Update content transmission items to have their respective catalog's uuid.
    # """

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
        # """
        # Update all past content transmission items to show end dates.
        # """

        # get the edx course id's for every course in canvas
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

        for canvas_channel in self.get_integrated_channels(options):
            transmitted_course_ids = ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=canvas_channel.enterprise_customer,
                integrated_channel_code='CANVAS',
                deleted_at__isnull=True,
            ).values('content_id')

            import pdb;
            pdb.set_trace();

            canvas_api_client = CanvasAPIClient(canvas_channel)
            for course_id in transmitted_course_ids:
                canvas_api_client.update_participation_types(course_id['content_id'])

    


        #     enterprise_customer_catalogs = canvas_channel.customer_catalogs_to_transmit or \
        #         canvas_channel.enterprise_customer.enterprise_customer_catalogs.all()
        #     for enterprise_customer_catalog in enterprise_customer_catalogs:
        #         content_keys = self._get_catalog_content_keys(enterprise_customer_catalog)

        # for course_key in content_keys:



        #     transmission_items = ContentMetadataItemTransmission.objects.filter(
        #         enterprise_customer=self.enterprise_configuration.enterprise_customer,
        #         integrated_channel_code=self.enterprise_configuration.channel_code(),
        #         content_id__in=content_ids
        #     )

    #using enterprise cust and integrated channel code  - >
    #  get all content metadata item transmission and 
    # create a unique list of content_id using a filter 

#     query_set = TableName.objects.filter(
#     field=value
# ).all().values('field name')


# class ContentMetadataItemTransmission(TimeStampedModel):

        # if not EnterpriseCustomerUser.objects.filter(enterprise_customer=enterprise, user_id=self._user_id).exists():
        #     raise forms.ValidationError(_("Wrong Enterprise"))