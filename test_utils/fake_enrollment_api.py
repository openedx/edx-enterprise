"""
Fake implementation of the Enrollment API.
"""

import datetime
import json
import re

from slumber.exceptions import HttpClientError

from django.conf import settings

COURSE_ID_REGEX = r'course-v.:[^/+]+\+[^/+]+\+[^/?]+$'

COURSE_DETAILS = {
    "course-v1:edX+DemoX+Demo_Course": {
        "course_id": "course-v1:edX+DemoX+Demo_Course",
        "course_start": "2013-02-05T05:00:00Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 0,
            "name": "Audit",
            "slug": "audit",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": False,
    },
    "course-v1:HarvardX+CoolScience+2016": {
        "course_id": "course-v1:HarvardX+CoolScience+2016",
        "course_start": "2016-12-02T22:07:04Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 0,
            "name": "Audit",
            "slug": "audit",
            "suggested_prices": "",
        }, {
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 100,
            "name": "Verified Certificate",
            "slug": "verified",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": False,
    },
    "course-v1:EnterpriseX+Training+2017": {
        "course_id": "course-v1:EnterpriseX+Training+2017",
        "course_start": "2017-01-01T00:00:00Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 10000,
            "name": "Proffessional Education",
            "slug": "professional",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": True,
    },
    "course-v1:Organization+DNDv2+T1": {
        "course_id": "course-v1:Organization+DNDv2+T1",
        "course_start": "2017-01-01T00:00:00Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 10000,
            "name": "Proffessional Education",
            "slug": "professional",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": True,
    },
    "course-v1:Organization+ENT-1+T1": {
        "course_id": "course-v1:Organization+DNDv2+T1",
        "course_start": "2017-01-01T00:00:00Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 10000,
            "name": "Proffessional Education",
            "slug": "professional",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": True,
    },
    "course-v1:Organization+VD1+VD1": {
        "course_id": "course-v1:Organization+DNDv2+T1",
        "course_start": "2017-01-01T00:00:00Z",
        "course_end": None,
        "course_modes": [{
            "currency": "usd",
            "description": None,
            "expiration_datetime": None,
            "min_price": 10000,
            "name": "Proffessional Education",
            "slug": "professional",
            "suggested_prices": "",
        }],
        "enrollment_start": None,
        "enrollment_end": None,
        "invite_only": True,
    },
}


def _raise_client_error(url, message, **kwargs):
    """
    Emulate a client error raised by edx_rest_api_client.
    """
    content = {"message": message}
    content.update(kwargs)
    raise HttpClientError(
        "Client Error 400: {}/{}".format(settings.ENTERPRISE_ENROLLMENT_API_URL, url),
        content=json.dumps(content).encode(),
    )


def get_course_details(course_id):
    """
    Fake implementation returning data from the COURSE_DETAILS dictionary.
    """
    if not re.match(COURSE_ID_REGEX, course_id):
        return None
    try:
        return COURSE_DETAILS[course_id]
    except KeyError:
        return None


def enroll_user_in_course(user, course_id, mode, cohort=None, enterprise_uuid=None):
    """
    Fake implementation.
    """
    try:
        course_details = COURSE_DETAILS[course_id]
    except KeyError:
        _raise_client_error(
            "enrollment", "No course '{}' found for enrollment".format(course_id)
        )
    available_modes = [m["slug"] for m in course_details["course_modes"]]
    if mode not in available_modes:
        _raise_client_error(
            "enrollment",
            "The [{}] course mode is expired or otherwise unavailable for course run [{}].".format(
                mode, course_id
            )
        )
    return {
        "user": user,
        "course_details": course_details,
        "is_active": True,
        "mode": mode,
        "cohort": cohort,
        "enterprise_uuid": enterprise_uuid,
        "created": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    }


def get_course_enrollment(username, course_id):
    """
    Fake implementation.
    """
    try:
        course_details = COURSE_DETAILS[course_id]
    except KeyError:
        _raise_client_error(
            "enrollment", "No course '{}' found for enrollment".format(course_id)
        )

    return {
        "user": username,
        "course_details": course_details,
        "is_active": True,
        "mode": 'verified',
        "created": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    }


def get_enrolled_courses(username):
    """
    Fake implementation.
    """
    return [
        get_course_enrollment(username, 'course-v1:edX+DemoX+Demo_Course'),
        get_course_enrollment(username, 'course-v1:HarvardX+CoolScience+2016')
    ]
