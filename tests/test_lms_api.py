# -*- coding: utf-8 -*-
"""
Tests for enterprise.lms_api.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import json

import responses
from pytest import raises
from requests.compat import urljoin

from django.conf import settings

from enterprise import lms_api
from enterprise.utils import NotConnectedToEdX

URL_BASE_NAMES = {
    'enrollment': settings.ENTERPRISE_ENROLLMENT_API_URL,
    'courses': settings.LMS_ROOT_URL + '/api/courses/v1/',
}


def _url(base_name, path):
    """
    Build a URL for the relevant API named by base_name.

    Args:
        base_name (str): A name to identify the root URL by
        path (str): The URL suffix to append to the base path
    """
    return urljoin(URL_BASE_NAMES[base_name], path)


@responses.activate  # pylint: disable=no-member
def test_enrollment_api_client():
    expected_response = {"message": "test"}
    responses.add(responses.GET, _url("enrollment", "test"), json=expected_response)  # pylint: disable=no-member
    client = lms_api.EnrollmentApiClient()
    actual_response = client.client.test.get()
    assert actual_response == expected_response
    request = responses.calls[0][0]  # pylint: disable=no-member
    assert request.headers['X-Edx-Api-Key'] == settings.EDX_API_KEY


@responses.activate  # pylint: disable=no-member
def test_get_enrollment_course_details():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {"course_id": course_id}
    responses.add(  # pylint: disable=no-member
        responses.GET,  # pylint: disable=no-member
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        json=expected_response
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == expected_response


@responses.activate  # pylint: disable=no-member
def test_enroll_user_in_course():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    expected_response = dict(user=user, course_details=course_details, mode=mode)
    responses.add(  # pylint: disable=no-member
        responses.POST,  # pylint: disable=no-member
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.enroll_user_in_course(user, course_id, mode)
    assert actual_response == expected_response
    request = responses.calls[0][0]  # pylint: disable=no-member
    assert json.loads(request.body) == expected_response


@responses.activate  # pylint: disable=no-member
def test_get_enrolled_courses():
    user = "some_user"
    course_id = "course-v1:edx+DemoX+Demo_Course"
    expected_response = [
        {
            "course_details": {
                "course_id": course_id
            }
        }
    ]
    responses.add(  # pylint: disable=no-member
        responses.GET,  # pylint: disable=no-member
        _url("enrollment", "enrollment") + '?user={}'.format(user),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_enrolled_courses(user)
    assert actual_response == expected_response


@responses.activate  # pylint: disable=no-member
def test_get_full_course_details():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {
        "name": "edX Demo Course"
    }
    responses.add(  # pylint: disable=no-member
        responses.GET,  # pylint: disable=no-member
        _url("courses", "courses/course-v1:edX+DemoX+Demo_Course/"),
        json=expected_response,
    )
    client = lms_api.CourseApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == expected_response


def test_enroll_locally_raises():
    with raises(NotConnectedToEdX):
        lms_api.enroll_user_in_course_locally(None, None, None)
