"""
Tests for enterprise.api_client.lms.py
"""

import json
import time
from unittest import mock
from urllib.parse import urljoin

import pytest
import requests
import responses
from pytest import raises
from requests.exceptions import HTTPError

from django.conf import settings

from enterprise.api_client import client as base_api
from enterprise.api_client import lms as lms_api
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


def mock_access_token_response():
    responses.add(
        responses.POST,
        urljoin(f"{settings.LMS_INTERNAL_ROOT_URL}/", "oauth2/access_token"),
        body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
        status=200,
    )


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_enrollment_course_details_with_exception():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        status=400
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_details(course_id)
    assert actual_response == {}


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_enroll_user_in_course():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    cohort = "masters"
    expected_response = dict(
        user=user,
        course_details=course_details,
        mode=mode,
        cohort=cohort,
        is_active=True,
        enterprise_uuid='None'
    )
    responses.add(
        responses.POST,
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.enroll_user_in_course(user, course_id, mode, cohort=cohort)
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert json.loads(request.body) == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_enrollment():
    for user in ["_some_user", "some_user"]:
        # It's important that we test for usernames that begin with '_'
        # to test the functionality of `_get_underscore_safe_endpoint()`.
        course_id = "course-v1:edX+DemoX+Demo_Course"
        course_details = {"course_id": course_id}
        mode = "audit"
        expected_response = dict(user=user, course_details=course_details, mode=mode)
        responses.add(
            responses.GET,
            _url(
                "enrollment",
                "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
            ),
            json=expected_response
        )
        mock_access_token_response()
        client = lms_api.EnrollmentApiClient()
        actual_response = client.get_course_enrollment(user, course_id)
        assert actual_response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_is_enrolled():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    is_active = True
    expected_response = dict(user=user, course_details=course_details, mode=mode, is_active=is_active)
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        json=expected_response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.is_enrolled(user, course_id)
    assert actual_response is True


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mock.patch('enterprise.api_client.lms.COURSE_MODE_SORT_ORDER', ['a', 'list', 'containing', 'most', 'of', 'the'])
@mock.patch('enterprise.api_client.lms.EXCLUDED_COURSE_MODES', ['course'])
def test_get_enrollment_course_modes():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    response = {
        "course_modes": [
            {'slug': 'course'},
            {'slug': 'a'},
            {'slug': 'containing'},
            {'slug': 'list'},
            {'slug': 'modes'},
        ]
    }
    expected_return = [
        {'slug': 'a'},
        {'slug': 'list'},
        {'slug': 'containing'},
        {'slug': 'modes'},
    ]
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        json=response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_modes(course_id)
    assert actual_response == expected_return


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mock.patch('enterprise.api_client.lms.COURSE_MODE_SORT_ORDER', ['a', 'list', 'containing', 'most', 'of', 'the'])
def test_has_course_modes():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    response = {
        "course_modes": [
            {'slug': 'course'},
            {'slug': 'a'},
            {'slug': 'containing'},
            {'slug': 'list'},
            {'slug': 'modes'},
        ]
    }
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        json=response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.has_course_mode(course_id, 'list')
    assert actual_response is True


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mock.patch('enterprise.api_client.lms.COURSE_MODE_SORT_ORDER', ['a', 'list', 'containing', 'most', 'of', 'the'])
@mock.patch('enterprise.api_client.lms.EXCLUDED_COURSE_MODES', ['course'])
def test_doesnt_have_course_modes():
    course_id = "course-v1:edX+DemoX+Demo_Course"
    response = {
        "course_modes": [
            {'slug': 'course'},
            {'slug': 'a'},
            {'slug': 'containing'},
            {'slug': 'list'},
            {'slug': 'modes'},
        ]
    }
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "course/{}".format(course_id),
        ),
        json=response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.has_course_mode(course_id, 'course')
    assert actual_response is False


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_enrollment_invalid():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        status=404,
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_enrollment(user, course_id)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_enrollment_not_found():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        body='',
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_course_enrollment(user, course_id)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_is_enrolled_false():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        status=404,
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.is_enrolled(user, course_id)
    assert actual_response is False


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_is_enrolled_but_not_active():
    user = "some_user"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    course_details = {"course_id": course_id}
    mode = "audit"
    is_active = False
    expected_response = dict(user=user, course_details=course_details, mode=mode, is_active=is_active)
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        json=expected_response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.is_enrolled(user, course_id)
    assert actual_response is False


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    actual_response = client.get_enrolled_courses(user)
    assert actual_response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_unenroll():
    user = "some_user"
    course_id = "course-v1:edx+DemoX+Demo_Course"
    mode = 'audit'
    is_active = True
    expected_response = dict(user=user, course_details={'course_id': course_id}, mode=mode, is_active=is_active)
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        json=expected_response
    )
    expected_response = dict(user=user, is_active=False)
    responses.add(
        responses.POST,
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    unenrolled = client.unenroll_user_from_course(user, course_id)
    assert unenrolled


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_update_course_enrollment_mode_for_user():
    user = "some_user"
    course_id = "course-v1:edx+DemoX+Demo_Course"
    mode = 'audit'
    expected_response = dict(user=user, course_details={'course_id': course_id}, mode=mode, is_active=False)
    responses.add(
        responses.POST,
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    expected_request_json = {
        'user': user,
        'course_details': {'course_id': course_id},
        'mode': mode,
    }
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    response = client.update_course_enrollment_mode_for_user(user, course_id, mode)
    request = responses.calls[-1].request
    assert json.loads(request.body) == expected_request_json
    assert response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_unenroll_already_unenrolled():
    user = "some_user"
    course_id = "course-v1:edx+DemoX+Demo_Course"
    mode = 'audit'
    expected_response = dict(user=user, course_details={'course_id': course_id}, mode=mode, is_active=False)
    responses.add(
        responses.GET,
        _url(
            "enrollment",
            "enrollment/{username},{course_id}".format(username=user, course_id=course_id),
        ),
        json=expected_response
    )
    expected_response = dict(user=user, is_active=False)
    responses.add(
        responses.POST,
        _url(
            "enrollment",
            "enrollment",
        ),
        json=expected_response
    )
    mock_access_token_response()
    client = lms_api.EnrollmentApiClient()
    unenrolled = client.unenroll_user_from_course(user, course_id)
    assert not unenrolled


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
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_remote_id(provider_id, username)
    assert actual_response == "LukeIamYrFather"


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@pytest.mark.parametrize('status', (400, 500))
def test_third_party_api_errors(status):
    username = "Darth"
    provider_id = "DeathStar"
    responses.add(
        responses.GET,
        _url("third_party_auth", f"providers/{provider_id}/users?username={username}"),
        match_querystring=True,
        status=status,
    )
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    with pytest.raises(HTTPError):
        client.connect()
        client._get_results(provider_id, 'username', username, 'remote_id')  # pylint: disable=protected-access


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_username_from_remote_id_not_found():
    remote_id = "Darth"
    provider_id = "DeathStar"
    responses.add(
        responses.GET,
        _url("third_party_auth", "providers/{provider}/users?remote_id={user}".format(
            provider=provider_id, user=remote_id
        )),
        match_querystring=True,
        status=404
    )
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_username_from_remote_id(provider_id, remote_id)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_username_from_remote_id_no_results():
    remote_id = "Darth"
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
        _url("third_party_auth", "providers/{provider}/users?remote_id={user}".format(
            provider=provider_id, user=remote_id
        )),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_username_from_remote_id(provider_id, remote_id)
    assert actual_response is None


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_username_from_remote_id():
    remote_id = "LukeIamYrFather"
    provider_id = "DeathStar"
    expected_response = {
        "page": 1,
        "page_size": 200,
        "count": 1,
        "results": [
            {"username": "Darth", "remote_id": "LukeIamYrFather"}
        ]
    }
    responses.add(
        responses.GET,
        _url("third_party_auth", "providers/{provider}/users?remote_id={user}".format(
            provider=provider_id, user=remote_id
        )),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.ThirdPartyAuthApiClient('staff-user-goes-here')
    actual_response = client.get_username_from_remote_id(provider_id, remote_id)
    assert actual_response == "Darth"


def test_jwt_lms_api_client_locally_raises():
    with raises(NotConnectedToOpenEdX):
        client = base_api.UserAPIClient('user-goes-here')
        client.connect()


@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_jwt_lms_api_client_refresh_token():

    class UserAPIClientTest(base_api.UserAPIClient):
        """
        Test the UserAPIClient class's expired token refreshing logic.
        """
        something_called = 0

        @base_api.UserAPIClient.refresh_token
        def something(self):
            """
            Tests the refresh_token decorator.
            """
            self.something_called += 1

    client = UserAPIClientTest('user-goes-here', expires_in=1)
    assert client.token_is_expired(), "Token is expired before connect"

    client.something()
    assert client.something_called == 1, "Wrapped method was called, token created"
    assert not client.token_is_expired(), "Token is not yet expired"

    client.something()
    assert client.something_called == 2, "Wrapped method was called, using existing token."
    assert not client.token_is_expired(), "Token is not yet expired"

    time.sleep(2)
    assert client.token_is_expired(), "Token is now expired"

    client.something()
    assert not client.token_is_expired(), "Token was refreshed"
    assert client.something_called == 3, "Wrapped method was called"


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_grades_not_found():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url("course_grades", "courses/{course}/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        status=404
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    with raises(HTTPError):
        client.get_course_grade(course_id, username)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
        _url("course_grades", "courses/{course}/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    with raises(HTTPError):
        client.get_course_grade(course_id, username)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
        _url("course_grades", "courses/{course}/?username={user}".format(course=course_id, user=username)),
        match_querystring=True,
        json=expected_response,
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    actual_response = client.get_course_grade(course_id, username)
    assert actual_response == expected_response[0]


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
    with raises(HTTPError):
        client.get_course_certificate(course_id, username)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_assessment_grades():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    expected_result = 'section_breakdown_content'
    response_body = {'results': [{'username': 'DarthVadar', 'section_breakdown': expected_result}]}
    responses.add(
        responses.GET,
        _url("course_grades", f"gradebook/{course_id}/?username={username}"),
        match_querystring=True,
        json=response_body,
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    actual_response = client.get_course_assessment_grades(course_id, username)
    assert actual_response == expected_result


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_course_assessment_grades_not_found():
    username = "DarthVadar"
    course_id = "course-v1:edX+DemoX+Demo_Course"
    responses.add(
        responses.GET,
        _url("course_grades", f"gradebook/{course_id}/?username={username}"),
        match_querystring=True,
        json={'results': [{'username': 'another_username'}]}
    )
    client = lms_api.GradesApiClient('staff-user-goes-here')
    with raises(HTTPError):
        client.get_course_assessment_grades(course_id, username)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
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
