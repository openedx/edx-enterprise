# -*- coding: utf-8 -*-
"""
Tests for enterprise.enrollment_api.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import json

import responses
from requests.compat import urljoin

from django.conf import settings

from enterprise import enrollment_api


def _url(path):
    """
    Build a URL for the enrollment API.
    """
    return urljoin(settings.ENTERPRISE_ENROLLMENT_API_URL, path)


@responses.activate  # pylint: disable=no-member
def test_get_enrollment_api_client():
    expected_response = {"message": "test"}
    responses.add(responses.GET, _url("test"), json=expected_response)  # pylint: disable=no-member
    client = enrollment_api.get_enrollment_api_client()
    actual_response = client.test.get()
    assert actual_response == expected_response
    request = responses.calls[0][0]  # pylint: disable=no-member
    assert request.headers['X-Edx-Api-Key'] == settings.EDX_API_KEY


@responses.activate  # pylint: disable=no-member
def test_get_course_details():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {"course_id": course_id}
    responses.add(  # pylint: disable=no-member
        responses.GET, _url("course/{}".format(course_id)), json=expected_response  # pylint: disable=no-member
    )
    actual_response = enrollment_api.get_course_details(course_id)
    assert actual_response == expected_response


@responses.activate  # pylint: disable=no-member
def test_enroll_user_in_course():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    expected_response = dict(user=user, course_details=course_details, mode=mode)
    responses.add(responses.POST, _url("enrollment"), json=expected_response)  # pylint: disable=no-member
    actual_response = enrollment_api.enroll_user_in_course(user, course_details, mode)
    assert actual_response == expected_response
    request = responses.calls[0][0]  # pylint: disable=no-member
    assert json.loads(request.body) == expected_response
