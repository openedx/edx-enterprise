"""
Content metadata exporter for Cornerstone.
"""

import datetime
from logging import getLogger

import pytz

from django.apps import apps
from django.conf import settings

from enterprise.utils import get_closest_course_run, get_language_code
from integrated_channels.cornerstone.utils import convert_invalid_course_id
from integrated_channels.integrated_channel.constants import ISO_8601_DATE_FORMAT
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.utils import (
    get_duration_from_estimated_hours,
    get_image_url,
    get_subjects_from_content_metadata,
)

LOGGER = getLogger(__name__)


class CornerstoneContentMetadataExporter(ContentMetadataExporter):
    """
    Cornerstone implementation of ContentMetadataExporter.
    """
    LONG_STRING_LIMIT = 10000
    DEFAULT_SUBJECT = "Industry Specific"
    DEFAULT_LANGUAGE = "English"
    DEFAULT_PARTNER = {
        "Name": "edX: edX Inc"
    }
    DATA_TRANSFORM_MAPPING = {
        'ID': 'key',
        'Title': 'title',
        'Description': 'description',
        'Thumbnail': 'image',
        'URL': 'enrollment_url',
        'IsActive': 'is_active',
        'LastModifiedUTC': 'modified',
        'Duration': 'estimated_hours',
        'Partners': 'organizations',
        'Languages': 'languages',
        'Subjects': 'subjects',
    }
    SKIP_KEY_IF_NONE = True
    MAX_PAYLOAD_COUNT = getattr(settings, "ENTERPRISE_CORNERSTONE_MAX_CONTENT_PAYLOAD_COUNT", 1000)

    def export_for_web_polling(self, max_payload_count=MAX_PAYLOAD_COUNT):  # pylint: disable=unused-argument
        """
        Return the exported and transformed content metadata as a dictionary for CSDO web pull.
        """
        ContentMetadataItemTransmission = apps.get_model(
            'integrated_channel',
            'ContentMetadataItemTransmission'
        )
        create_payload = ContentMetadataItemTransmission.objects.filter(
            marked_for='create',
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            plugin_configuration_id=self.enterprise_configuration.id,
        )
        update_payload = ContentMetadataItemTransmission.objects.filter(
            marked_for='update',
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            plugin_configuration_id=self.enterprise_configuration.id,
        )
        delete_payload = ContentMetadataItemTransmission.objects.filter(
            marked_for='delete',
            enterprise_customer=self.enterprise_configuration.enterprise_customer,
            plugin_configuration_id=self.enterprise_configuration.id,
        )
        created = {record.content_id: record for record in create_payload}
        updated = {record.content_id: record for record in update_payload}
        deleted = {record.content_id: record for record in delete_payload}
        return created, updated, deleted

    def transform_courserun_key(self, content_metadata_item):
        """
        Return the transformed version of the course run key by converting into a string of valid chars by encoding the
        key with base 64. Because valid course run keys have already been transmitted as courses, and course keys are
        used to uniquely identify edx courses, we only want to encode the invalid ones as they would have never been
        created.
        """
        return convert_invalid_course_id(content_metadata_item.get('key'))

    def transform_course_key(self, content_metadata_item):
        """
        Return the transformed version of the course key by converting into a string of valid chars by encoding the key
        with base 64
        """
        return convert_invalid_course_id(content_metadata_item.get('key'))

    def transform_organizations(self, content_metadata_item):
        """
        Return the transformed version of the course organizations by converting each organization into cornerstone
        course partner object. or default Partner if no partner found
        """
        partners = []
        for org in content_metadata_item.get('organizations') or []:
            org_name = org[:500] if org else ''
            partners.append({"Name": org_name})
        return partners or [self.DEFAULT_PARTNER]

    def transform_is_active(self, content_metadata_item):
        """
        Return the transformed version of the course is_active status by traversing course runs and setting IsActive to
        True if any of the course runs have availability value set to `Current`, `Starting Soon` or `Upcoming`.
        """
        is_active = False
        for course_run in content_metadata_item.get('course_runs', []):
            if course_run.get('availability') in ['Current', 'Starting Soon', 'Upcoming']:
                is_active = True
                break
        return is_active

    def transform_modified(self, content_metadata_item):
        """
        Return the modified datetime of closest course run`.
        """
        modified_datetime = datetime.datetime.now(pytz.UTC).strftime(ISO_8601_DATE_FORMAT)
        course_runs = content_metadata_item.get('course_runs')
        if course_runs:
            closest_course_run = get_closest_course_run(course_runs)
            modified_datetime = closest_course_run.get('modified', modified_datetime)

        return str(modified_datetime)

    def transform_estimated_hours(self, content_metadata_item):
        """
        Return the duration of course in hh:mm:ss format.
        """
        duration = None
        course_runs = content_metadata_item.get('course_runs')
        if course_runs:
            closest_course_run = get_closest_course_run(course_runs)
            estimated_hours = closest_course_run.get('estimated_hours')
            duration = get_duration_from_estimated_hours(estimated_hours)

        return duration

    def transform_image(self, content_metadata_item):
        """
        Return the image URI of the content item.
        """
        return get_image_url(content_metadata_item)

    def transform_languages(self, content_metadata_item):
        """
        Return the languages supported by course or `English` as default if no languages found.
        """
        CornerstoneGlobalConfiguration = apps.get_model(
            'cornerstone',
            'CornerstoneGlobalConfiguration'
        )
        languages_json = CornerstoneGlobalConfiguration.current().languages or {'Languages': []}

        languages = content_metadata_item.get('languages') or [self.DEFAULT_LANGUAGE]
        course_languages = [get_language_code(language) for language in languages]
        languages = set(languages_json['Languages']).intersection(set(course_languages))
        return list(languages) if languages else ['en-US']

    def transform_description(self, content_metadata_item):
        """
        Return the transformed version of the course description.

        We choose one value out of the course's full description, short description, and title depending on availability
        and length limits.
        """
        full_description = content_metadata_item.get('full_description') or ''
        if 0 < len(full_description) <= self.LONG_STRING_LIMIT:
            return full_description
        return content_metadata_item.get('short_description') or content_metadata_item.get('title') or ''

    def transform_subjects(self, content_metadata_item):
        """
        Return the transformed version of the course subject list or default value if no subject found.
        """
        if self.enterprise_configuration.disable_subject_metadata_transmission:
            return None
        subjects = []
        course_subjects = get_subjects_from_content_metadata(content_metadata_item)
        CornerstoneGlobalConfiguration = apps.get_model(
            'cornerstone',
            'CornerstoneGlobalConfiguration'
        )
        subjects_mapping_dict = CornerstoneGlobalConfiguration.current().subject_mapping or {}
        for subject in course_subjects:
            for cornerstone_subject, edx_subjects in subjects_mapping_dict.items():
                if subject.lower() in [edx_subject.lower() for edx_subject in edx_subjects]:
                    subjects.append(cornerstone_subject)
        return list(set(subjects)) or [self.DEFAULT_SUBJECT]
