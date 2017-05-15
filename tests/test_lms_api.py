# -*- coding: utf-8 -*-
"""
Tests for enterprise.lms_api.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import json
import time

import mock
import requests
import responses
from pytest import raises
from slumber.exceptions import HttpNotFoundError

from django.conf import settings

from enterprise import lms_api
from enterprise.utils import NotConnectedToOpenEdX

URL_BASE_NAMES = {
    'enrollment': lms_api.EnrollmentApiClient,
    'courses': lms_api.CourseApiClient,
    'third_party_auth': lms_api.ThirdPartyAuthApiClient,
    'course_grades': lms_api.GradesApiClient,
    'certificates': lms_api.CertificatesApiClient,
}


def _url(base_name, path):
    """
    Build a URL for the relevant API named by base_name.

    Args:
        base_name (str): A name to identify the root URL by
        path (str): The URL suffix to append to the base path
    """
    return requests.compat.urljoin(URL_BASE_NAMES[base_name].API_BASE_URL, path)


@responses.activate
def test_enrollment_api_client():
    expected_response = {"message": "test"}
    responses.add(responses.GET, _url("enrollment", "test"), json=expected_response)
    client = lms_api.EnrollmentApiClient()
    actual_response = client.client.test.get()
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert request.headers['X-Edx-Api-Key'] == settings.EDX_API_KEY


@responses.activate
def test_get_enrollment_course_details():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {"course_id": course_id}
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        json=expected_response
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == expected_response


@responses.activate
def test_enroll_user_in_course():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    expected_response = dict(user=user, course_details=course_details, mode=mode)
    responses.add(
        responses.POST,
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.enroll_user_in_course(user, course_id, mode)
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert json.loads(request.body) == expected_response


@responses.activate
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
    responses.add(
        responses.GET,
        _url("enrollment", "enrollment") + '?user={}'.format(user),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_enrolled_courses(user)
    assert actual_response == expected_response


def test_enroll_locally_raises():
    with raises(NotConnectedToOpenEdX):
        lms_api.enroll_user_in_course_locally(None, None, None)


@responses.activate
def test_get_full_course_details():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {
        "name": "edX Demo Course"
    }
    responses.add(
        responses.GET,
        _url("courses", "courses/course-v1:edX+DemoX+Demo_Course/"),
        json=expected_response,
    )
    client = lms_api.CourseApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == expected_response


@responses.activate
def test_get_full_course_details_not_found():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url("courses", "courses/course-v1:edX+DemoX+Demo_Course/"),
        status=404,
    )
    client = lms_api.CourseApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response is None


@responses.activate
def test_get_remote_id_not_found():
    username = "Darth"
    provider_id = "DeathStar"
    responses.add(
        responses.GET,
        _url("third_party_auth", "providers/{provider}/users?username={user}".format(
            provider=provider_id, user=username
        )),
        match_querystring=True,
        status=404
    )
    client = lms_api.ThirdPartyAuthApiClient()
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response is None


@responses.activate
def test_get_remote_id_no_results():
    username = "Darth"
    provider_id = "DeathStar"
    expected_response = {
        "page": 1,
        "page_size": 200,
        "count": 2,
        "results": [
            {"username": "Obi-Wan", "remote_id": "Kenobi"},
            {"username": "Hans", "remote_id": "Solo"},
        ]
    }
    responses.add(
        responses.GET,
        _url("third_party_auth", "providers/{provider}/users?username={user}".format(
            provider=provider_id, user=username
        )),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.ThirdPartyAuthApiClient()
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response is None


@responses.activate
def test_get_remote_id():
    username = "Darth"
    provider_id = "DeathStar"
    expected_response = {
        "page": 1,
        "page_size": 200,
        "count": 2,
        "results": [
            {"username": "Darth", "remote_id": "LukeIamYrFather"},
            {"username": "Darth", "remote_id": "JamesEarlJones"},
        ]
    }
    responses.add(
        responses.GET,
        _url("third_party_auth", "providers/{provider}/users?username={user}".format(
            provider=provider_id, user=username
        )),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.ThirdPartyAuthApiClient()
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response == "LukeIamYrFather"


def test_jwt_lms_api_client_locally_raises():
    with raises(NotConnectedToOpenEdX):
        client = lms_api.JwtLmsApiClient('user-goes-here')
        client.connect()


@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_jwt_lms_api_client_refresh_token():

    class JwtLmsApiClientTest(lms_api.JwtLmsApiClient):
        """
        Test the JwtLmsApiClient class's expired token refreshing logic.
        """
        something_called = 0

        @lms_api.JwtLmsApiClient.refresh_token
        def something(self):
            """
            Tests the refresh_token decorator.
            """
            self.something_called += 1

    client = JwtLmsApiClientTest('user-goes-here', expires_in=1)
    assert client.token_expired(), "Token is expired before connect"

    client.something()
    assert client.something_called == 1, "Wrapped method was called, token created"
    assert not client.token_expired(), "Token is not yet expired"

    client.something()
    assert client.something_called == 2, "Wrapped method was called, using existing token."
    assert not client.token_expired(), "Token is not yet expired"

    time.sleep(2)
    assert client.token_expired(), "Token is now expired"

    client.something()
    assert not client.token_expired(), "Token was refreshed"
    assert client.something_called == 3, "Wrapped method was called"


@responses.activate
@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_get_course_grades_not_found():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url("course_grades", "course_grade/{course}/users/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        status=404
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    with raises(HttpNotFoundError):
        client.get_course_grade(course_id, username)


@responses.activate
@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_get_course_grade_no_results():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = [{
        "username": "bob",
        "course_key": "edX/DemoX/Demo_Course",
        "passed": False,
        "percent": 0.03,
        "letter_grade": None,
    }]
    responses.add(
        responses.GET,
        _url("course_grades", "course_grade/{course}/users/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    with raises(HttpNotFoundError):
        client.get_course_grade(course_id, username)


@responses.activate
@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_get_course_grade():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = [{
        "username": username,
        "course_key": "edX/DemoX/Demo_Course",
        "passed": True,
        "percent": 0.75,
        "letter_grade": 'C',
    }]
    responses.add(
        responses.GET,
        _url("course_grades", "course_grade/{course}/users/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    actual_response = client.get_course_grade(course_id, username)
    assert actual_response == expected_response[0]


@responses.activate
@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_get_course_certificate_not_found():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url("certificates", "certificates/{user}/courses/{course}/".format(course=course_id, user=username)),
        match_querystring=True,
        status=404
    )
    client = lms_api.CertificatesApiClient('staff-user-goes-here')
    with raises(HttpNotFoundError):
        client.get_course_certificate(course_id, username)


@responses.activate
@mock.patch('enterprise.lms_api.JwtBuilder', mock.Mock())
def test_get_course_certificate():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_response = {
        "username": username,
        "course_id": course_id,
        "certificate_type": "professional",
        "status": "downloadable",
        "is_passing": True,
        "grade": '0.88',
    }
    responses.add(
        responses.GET,
        _url("certificates", "certificates/{user}/courses/{course}/".format(course=course_id, user=username)),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.CertificatesApiClient('staff-user-goes-here')
    actual_response = client.get_course_certificate(course_id, username)
    assert actual_response == expected_response
