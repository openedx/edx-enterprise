# -*- coding: utf-8 -*-
"""
Test utilities.
"""
# Since py.test discourages putting __init__.py into test directory (i.e. making tests a package)
# one cannot import from anywhere under tests folder. However, some utility classes/methods might be useful
# in multiple test modules. So this package the place to put them.

from __future__ import absolute_import, unicode_literals

import copy
import json
import uuid

from django.conf import settings
from django.core.urlresolvers import reverse

import mock
import six
from pytest import mark
from rest_framework.test import APITestCase, APIClient
from six.moves.urllib.parse import parse_qs, urljoin, urlsplit  # pylint: disable=import-error,ungrouped-imports

from django.shortcuts import render

from test_utils import factories
from enterprise import utils

FAKE_UUIDS = [str(uuid.uuid4()) for i in range(5)]  # pylint: disable=no-member
TEST_USERNAME = 'api_worker'
TEST_EMAIL = 'test@email.com'
TEST_PASSWORD = 'QWERTY'
TEST_COURSE = 'course-v1:edX+DemoX+Demo_Course'
TEST_UUID = 'd2098bfb-2c78-44f1-9eb2-b94475356a3f'
TEST_USER_ID = 1


def get_magic_name(value):
    """
    Return value suitable for __name__ attribute.

    For python2, __name__ must be str, while for python3 it must be unicode (as there are no str at all).

    Arguments:
        value basestring: string to "convert"

    Returns:
        str or unicode
    """
    return str(value) if six.PY2 else value


def mock_view_function():
    """
    Return mock function for views that are decorated.
    """
    view_function = mock.Mock()
    view_function.__name__ = str('view_function') if six.PY2 else 'view_function'
    return view_function


def create_items(factory, items):
    """
    Create model instances using given factory.
    """
    for item in items:
        factory.create(**item)


def update_course_run_with_enterprise_context(course_run, add_utm_info=True):
    """
    Populate a fake course run response with any necessary Enterprise context for testing purposes.

    Arguments:
        course_run (dict): The course_run to populate with enterprise context.
        add_utm_info(bool): control to utm information.
    """
    enterprise_utm_context = {
        'utm_medium': 'enterprise',
        'utm_source': 'test_enterprise'
    }
    url = urljoin(
        settings.LMS_ROOT_URL,
        reverse(
            'enterprise_course_enrollment_page',
            kwargs={'enterprise_uuid': FAKE_UUIDS[0], 'course_id': course_run['key']}
        )
    )
    course_run['enrollment_url'] = utils.update_query_parameters(url, enterprise_utm_context) if add_utm_info else url


def update_program_with_enterprise_context(program, add_utm_info=True):
    """
    Populate a fake program response with any necessary Enterprise context for testing purposes.

    Arguments:
        program (dict): The program to populate with enterprise context.
        add_utm_info (bool): control to utm information.
    """
    enterprise_utm_context = {
        'utm_medium': 'enterprise',
        'utm_source': 'test_enterprise'
    }
    url = urljoin(
        settings.LMS_ROOT_URL,
        reverse(
            'enterprise_program_enrollment_page',
            kwargs={'enterprise_uuid': FAKE_UUIDS[0], 'program_uuid': program['uuid']}
        )
    )
    program['enrollment_url'] = utils.update_query_parameters(url, enterprise_utm_context) if add_utm_info else url
    for course in program.get('courses', []):
        for course_run in course['course_runs']:
            update_course_run_with_enterprise_context(course_run)


def update_search_with_enterprise_context(search_result, add_utm_info):
    """
    Populate fake discovery search result response with any necessary Enterprise context for testing purposes.

    Arguments:
        search_result (dict): The search result to populate with enterprise context.
    """
    search_result = copy.deepcopy(search_result)
    for item in search_result['results']:
        content_type = item['content_type']
        if content_type == 'program':
            update_program_with_enterprise_context(item, add_utm_info)
        elif content_type == 'courserun':
            update_course_run_with_enterprise_context(item, add_utm_info)
    return search_result


def fake_render(request, template, context):  # pylint: disable=unused-argument
    """
    Switch the request to use a template that does not depend on edx-platform.
    """
    return render(request, 'enterprise/emails/user_notification.html', context=context)


def assert_url(first, second):
    """
    Compare first and second url.

    Arguments:
        first (str) : first url.
        second (str) : second url.

    Raises:
        Assertion error if both urls do not match.

    """
    # Convert query paramters to a dictionary, so that they can be compared correctly
    scheme, netloc, path, query_string, fragment = urlsplit(first)
    first = (scheme, netloc, path, parse_qs(query_string), fragment)

    # Convert query paramters to a dictionary, so that they can be compared correctly
    scheme, netloc, path, query_string, fragment = urlsplit(second)
    second = (scheme, netloc, path, parse_qs(query_string), fragment)

    assert first == second


@mark.django_db
class APITest(APITestCase):
    """
    Base class for API Tests.
    """

    def setUp(self):
        """
        Perform operations common to all tests.
        """
        super(APITest, self).setUp()
        self.create_user(username=TEST_USERNAME, password=TEST_PASSWORD)
        self.client = APIClient()
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        super(APITest, self).tearDown()

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, **kwargs)
        self.user.set_password(password)  # pylint: disable=no-member
        self.user.save()  # pylint: disable=no-member

    def load_json(self, content):
        """
        Parse content from django Response object.

        Arguments:
            content (bytes | str) : content type id bytes for PY3 and is string for PY2

        Returns:
            dict object containing parsed json from response.content

        """
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return json.loads(content)
