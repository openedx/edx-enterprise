"""
Assign skills to degreed courses
"""
from logging import getLogger

from requests.exceptions import ConnectionError, RequestException, Timeout  # pylint: disable=redefined-builtin

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from integrated_channels.degreed2.client import Degreed2APIClient
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.utils import generate_formatted_log

User = auth.get_user_model()
LOGGER = getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Add skill metadata to existing Degreed courses.

    ./manage.py lms assign_skills_to_degreed_courses
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
            help='Use this user to access the Enterprise Catalog API.'
        )
        super().add_arguments(parser)

    def _prepare_json_payload_for_skills_endpoint(self, course_skills):
        """
        Prepares a json payload for skills in the Degreed expected format.
        """
        course_skills_json = []
        for skill in course_skills:
            skill_data = {"type": "skills", "id": skill}
            course_skills_json.append(skill_data)
        return {
            "data": course_skills_json
        }

    def handle(self, *args, **options):
        """
        Update all existing Degreed courses to assign skills metadata.
        """
        options['channel'] = 'DEGREED2'
        username = options['catalog_user']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as no_user_error:
            raise CommandError('A user with the username {} was not found.'.format(username)) from no_user_error

        enterprise_catalog_client = EnterpriseCatalogApiClient(user)
        integrated_channels = self.get_integrated_channels(options)
        for degreed_channel_config in integrated_channels:
            enterprise_customer = degreed_channel_config.enterprise_customer
            enterprise_customer_catalogs = degreed_channel_config.customer_catalogs_to_transmit or \
                enterprise_customer.enterprise_customer_catalogs.all()
            try:
                content_metadata_in_catalogs = enterprise_catalog_client.get_content_metadata(
                    enterprise_customer,
                    enterprise_customer_catalogs
                )
            except (RequestException, ConnectionError, Timeout) as exc:
                LOGGER.exception(
                    'Failed to retrieve enterprise catalogs content metadata due to: [%s]', str(exc)
                )
                continue

            degreed_client = Degreed2APIClient(degreed_channel_config)
            LOGGER.info(
                generate_formatted_log(
                    degreed_channel_config.channel_code(),
                    enterprise_customer.uuid,
                    None,
                    None,
                    f'[Degreed Skills] Attempting to assign skills for customer {enterprise_customer.slug}'
                )
            )

            for content_item in content_metadata_in_catalogs:
                course_id = content_item.get('key', None)
                course_skills = content_item.get('skill_names', [])

                # if we get empty list of skills, there's no point making API call to Degreed.
                if not course_skills:
                    continue

                json_payload = self._prepare_json_payload_for_skills_endpoint(course_skills)

                # assign skills metadata to degreed course by first fetching degreed course id
                try:
                    degreed_client.assign_course_skills(course_id, json_payload)
                except ClientError as error:
                    LOGGER.error(
                        generate_formatted_log(
                            degreed_channel_config.channel_code(),
                            enterprise_customer.uuid,
                            None,
                            None,
                            f'Degreed2APIClient assign_course_skills failed for course {course_id} '
                            f'with message: {error.message}'
                        )
                    )
                    continue
                except RequestException as error:
                    LOGGER.error(
                        generate_formatted_log(
                            degreed_channel_config.channel_code(),
                            enterprise_customer.uuid,
                            None,
                            None,
                            f'Degreed2APIClient request to assign skills failed with message: {error.message}'
                        )
                    )
                    continue
