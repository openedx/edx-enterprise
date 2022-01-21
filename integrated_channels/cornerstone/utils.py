"""
Utilities for Cornerstone integrated channels.
"""

from logging import getLogger
from uuid import uuid4

from django.apps import apps


def cornerstone_learner_data_transmission_audit():
    """
        Returns the ``CornerstoneLearnerDataTransmissionAudit`` class.
    """
    return apps.get_model('cornerstone', 'CornerstoneLearnerDataTransmissionAudit')


def cornerstone_course_key_model():
    """
        Returns the ``CornerstoneCourseKey`` class.
    """
    return apps.get_model('cornerstone', 'CornerstoneCourseKey')


LOGGER = getLogger(__name__)


def create_cornerstone_learner_data(request, course_id):
    """
        updates or creates CornerstoneLearnerDataTransmissionAudit
    """
    try:
        defaults = {
            'user_guid': request.GET['userGuid'],
            'session_token': request.GET['sessionToken'],
            'callback_url': request.GET['callbackUrl'],
            'subdomain': request.GET['subdomain'],
        }
        cornerstone_learner_data_transmission_audit().objects.update_or_create(
            user_id=request.user.id,
            course_id=course_id,
            defaults=defaults
        )
    except KeyError:
        # if we couldn't find a key, it means we don't want to save data. just skip it by doing nothing.
        pass
    except Exception as ex:  # pylint: disable=broad-except
        LOGGER.error('Unable to Create/Update CornerstoneLearnerDataTransmissionAudit. {ex}'.format(ex=ex))


def convert_invalid_course_id(course_id):
    """
        upsert a CornerstoneCourseKey object, return the external_course_id
    """
    key_mapping = get_or_create_key_pair(course_id)
    return key_mapping.external_course_id


def get_or_create_key_pair(course_id):
    """
        upsert and return a CornerstoneCourseKey object, always use uuid4 for new external_course_id records
        old records may contain: an internal course_id, a base64 encoded internal course_id, a non-hyphenated uuid4
    """
    key_mapping, ___ = cornerstone_course_key_model().objects.get_or_create(
        internal_course_id=course_id, defaults={
            'external_course_id': str(uuid4())})
    return key_mapping
