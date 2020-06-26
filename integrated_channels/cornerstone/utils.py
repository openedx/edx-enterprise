# -*- coding: utf-8 -*-
"""
Utilities for Cornerstone integrated channels.
"""

from logging import getLogger

from integrated_channels.cornerstone.models import CornerstoneLearnerDataTransmissionAudit

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
        CornerstoneLearnerDataTransmissionAudit.objects.update_or_create(
            user_id=request.user.id,
            course_id=course_id,
            defaults=defaults
        )
    except KeyError:
        # if we couldn't find a key, it means we don't want to save data. just skip it by doing nothing.
        pass
    except Exception as ex:  # pylint: disable=broad-except
        LOGGER.error('Unable to Create/Update CornerstoneLearnerDataTransmissionAudit. {ex}'.format(ex=ex))
