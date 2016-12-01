# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

import requests
from edx_rest_api_client.client import EdxRestApiClient

from django.conf import settings


def get_enrollment_api_client():
    """
    Retrieve a client of the Enrollment API.

    The client is authenticated using the API token from the Django settings.
    """
    session = requests.Session()
    session.headers = {"X-Edx-Api-Key": settings.EDX_API_KEY}
    return EdxRestApiClient(
        settings.ENTERPRISE_ENROLLMENT_API_URL, append_slash=False, session=session
    )


def get_course_details(course_id):
    """
    Query the Enrollment API for the course details of the given course_id.
    """
    client = get_enrollment_api_client()
    return client.course(course_id).get()


def enroll_user_in_course(user, course_details, mode):
    """
    Query the enrollment API to enroll the user in the course specified by course_details.
    """
    client = get_enrollment_api_client()
    return client.enrollment.post(dict(user=user, course_details=course_details, mode=mode))
