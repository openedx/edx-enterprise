# -*- coding: utf-8 -*-
"""
Utilities for Cornerstone integrated channels.
"""

import re
from logging import getLogger
from uuid import uuid4

from django.apps import apps

from integrated_channels.utils import encode_course_key_into_base64


def cornerstone_learner_data_transmission_audit():
    """
    Returns the ``EnterpriseCustomer`` class.
    """
    return apps.get_model('cornerstone', 'CornerstoneLearnerDataTransmissionAudit')


def cornerstone_course_key_model():
    """
    Returns the ``EnterpriseCustomer`` class.
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
    Regex check a course ID to see if it contains any invalid chars. If it does then encode the string, otherwise
    return the original course ID.
    """
    safe_course_id = course_id
    re2 = re.compile(r"[|<>.&%\s\\/\“]+")
    if re2.search(safe_course_id):
        # If the course key contains any of the invalid chars, encode the key
        safe_course_id = encode_course_key_into_base64(course_id)
    # If the encoded or unencoded version of the key are over 50 characters, they will error out
    # in cornerstone, so we convert them to a uuid.
    if len(safe_course_id) > 50:
        safe_course_id = str(uuid4())
    return safe_course_id


def get_or_create_key_pair(course_id):
    key_mapping, ___ = cornerstone_course_key_model().objects.get_or_create(
        internal_course_id=course_id, defaults={
            'external_course_id': convert_invalid_course_id(course_id)})
    return key_mapping
