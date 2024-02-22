"""
Test utilities.
"""
# Since py.test discourages putting __init__.py into test directory (i.e. making tests a package)
# one cannot import from anywhere under tests folder. However, some utility classes/methods might be useful
# in multiple test modules. So this package the place to put them.


import copy
import json
import logging
import os
import tempfile
import uuid
from unittest import mock
from urllib.parse import parse_qs, urljoin, urlparse, urlsplit

from edx_rest_framework_extensions.auth.jwt.cookies import jwt_cookie_name
from edx_rest_framework_extensions.auth.jwt.tests.utils import generate_jwt_token, generate_unversioned_payload
from pytest import mark
from rest_framework.test import APIClient, APITestCase

from django.conf import settings
from django.core.cache import caches
from django.shortcuts import render
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from enterprise import utils
from test_utils import factories

FAKE_UUIDS = [str(uuid.uuid4()) for i in range(5)]
TEST_USERNAME = 'api_worker'
TEST_EMAIL = 'test@email.com'
TEST_PASSWORD = 'QWERTY'
TEST_COURSE = 'course-v1:edX+DemoX+Demo_Course'
TEST_COURSE_KEY = 'edX+DemoX'
TEST_UUID = 'd2098bfb-2c78-44f1-9eb2-b94475356a3f'
TEST_USER_ID = 1
TEST_SLUG = 'test-enterprise-customer'
TEST_PGP_KEY = """
-----BEGIN PGP PRIVATE KEY BLOCK-----
Comment: Alice's OpenPGP Transferable Secret Key
Comment: https://www.ietf.org/id/draft-bre-openpgp-samples-01.html
lFgEXEcE6RYJKwYBBAHaRw8BAQdArjWwk3FAqyiFbFBKT4TzXcVBqPTB3gmzlC/U
b7O1u10AAP9XBeW6lzGOLx7zHH9AsUDUTb2pggYGMzd0P3ulJ2AfvQ4RtCZBbGlj
ZSBMb3ZlbGFjZSA8YWxpY2VAb3BlbnBncC5leGFtcGxlPoiQBBMWCAA4AhsDBQsJ
CAcCBhUKCQgLAgQWAgMBAh4BAheAFiEE64W7X6M6deFelE5j8jFVDE9H444FAl2l
nzoACgkQ8jFVDE9H447pKwD6A5xwUqIDprBzrHfahrImaYEZzncqb25vkLV2arYf
a78A/R3AwtLQvjxwLDuzk4dUtUwvUYibL2sAHwj2kGaHnfICnF0EXEcE6RIKKwYB
BAGXVQEFAQEHQEL/BiGtq0k84Km1wqQw2DIikVYrQrMttN8d7BPfnr4iAwEIBwAA
/3/xFPG6U17rhTuq+07gmEvaFYKfxRB6sgAYiW6TMTpQEK6IeAQYFggAIBYhBOuF
u1+jOnXhXpROY/IxVQxPR+OOBQJcRwTpAhsMAAoJEPIxVQxPR+OOWdABAMUdSzpM
hzGs1O0RkWNQWbUzQ8nUOeD9wNbjE3zR+yfRAQDbYqvtWQKN4AQLTxVJN5X5AWyb
Pnn+We1aTBhaGa86AQ==
=n8OM
-----END PGP PRIVATE KEY BLOCK-----
"""


def get_magic_name(value):
    """
    Return value suitable for __name__ attribute.

    For python2, __name__ must be str, while for python3 it must be unicode (as there are no str at all).

    Arguments:
        value basestring: string to "convert"

    Returns:
        str or unicode
    """
    return value


def mock_view_function():
    """
    Return mock function for views that are decorated.
    """
    view_function = mock.Mock()
    view_function.__name__ = 'view_function'
    return view_function


def create_items(factory, items):
    """
    Create model instances using given factory.
    """
    for item in items:
        factory.create(**item)


def update_url_with_enterprise_context(url, add_utm_info=True, enterprise_catalog_uuid=None):
    """
    Append enterprise-related query parameters to the given URL.
    """
    query_params = {}

    if enterprise_catalog_uuid:
        query_params['catalog'] = enterprise_catalog_uuid

    if add_utm_info:
        query_params['utm_medium'] = 'enterprise'
        query_params['utm_source'] = 'test_enterprise'

    url = utils.update_query_parameters(url, query_params)
    return url


def update_course_run_with_enterprise_context(course_run, add_utm_info=True, enterprise_catalog_uuid=None):
    """
    Populate a fake course run response with any necessary Enterprise context for testing purposes.
    """
    url = urljoin(
        settings.LMS_ROOT_URL,
        reverse(
            'enterprise_course_run_enrollment_page',
            kwargs={'enterprise_uuid': FAKE_UUIDS[0], 'course_id': course_run['key']}
        )
    )

    course_run['enrollment_url'] = update_url_with_enterprise_context(
        url,
        add_utm_info=add_utm_info,
        enterprise_catalog_uuid=enterprise_catalog_uuid
    )

    return course_run


def update_course_with_enterprise_context(
        course,
        add_utm_info=True,
        enterprise_catalog_uuid=None,
        add_active_info=True,
        add_end_date_info=True
):
    """
    Populate a fake course response with any necessary Enterprise context for testing purposes.
    """
    url = urljoin(
        settings.LMS_ROOT_URL,
        reverse(
            'enterprise_course_enrollment_page',
            kwargs={'enterprise_uuid': FAKE_UUIDS[0], 'course_key': course['key']}
        )
    )

    course['enrollment_url'] = update_url_with_enterprise_context(
        url,
        add_utm_info=add_utm_info,
        enterprise_catalog_uuid=enterprise_catalog_uuid
    )

    course_runs = course.get('course_runs', [])

    if add_active_info:
        course['active'] = utils.has_course_run_available_for_enrollment(course_runs)
    if add_end_date_info:
        course['end_date'] = utils.get_last_course_run_end_date(course_runs)
    for course_run in course_runs:
        update_course_run_with_enterprise_context(
            course_run,
            add_utm_info=add_utm_info,
            enterprise_catalog_uuid=enterprise_catalog_uuid
        )

    return course


def update_program_with_enterprise_context(program, add_utm_info=True, enterprise_catalog_uuid=None):
    """
    Populate a fake program response with any necessary Enterprise context for testing purposes.
    """
    url = urljoin(
        settings.LMS_ROOT_URL,
        reverse(
            'enterprise_program_enrollment_page',
            kwargs={'enterprise_uuid': FAKE_UUIDS[0], 'program_uuid': program['uuid']}
        )
    )

    program['enrollment_url'] = update_url_with_enterprise_context(
        url,
        add_utm_info=add_utm_info,
        enterprise_catalog_uuid=enterprise_catalog_uuid
    )

    for course in program.get('courses', []):
        update_course_with_enterprise_context(
            course,
            add_utm_info=add_utm_info,
            enterprise_catalog_uuid=enterprise_catalog_uuid,
            add_active_info=False,
            add_end_date_info=False
        )

    return program


def update_search_with_enterprise_context(search_result, add_utm_info):
    """
    Populate fake discovery search result response with any necessary Enterprise context for testing purposes.

    Arguments:
        search_result (dict): The search result to populate with enterprise context.
        add_utm_info: UTM Info to replace
    """
    search_result = copy.deepcopy(search_result)
    for item in search_result['results']:
        content_type = item['content_type']
        if content_type == 'program':
            update_program_with_enterprise_context(item, add_utm_info)
        elif content_type == 'course':
            update_course_with_enterprise_context(item, add_utm_info)
        elif content_type == 'courserun':
            update_course_run_with_enterprise_context(item, add_utm_info)
    return search_result


def fake_render(request, template, context, **kwargs):  # pylint: disable=unused-argument
    """
    Switch the request to use a template that does not depend on edx-platform.
    The choice of the template here is arbitrary, as long as it renders successfully for tests.
    """
    return render(request, 'enterprise/_data_sharing_decline_modal.html', context=context)


def assert_url(first, second):
    """
    Compare first and second url.

    Arguments:
        first (str) : first url.
        second (str) : second url.

    Raises:
        Assertion error if both urls do not match.

    """
    # Convert query parameters to a dictionary, so that they can be compared correctly
    scheme, netloc, path, query_string, fragment = urlsplit(first)
    first = (scheme, netloc, path, parse_qs(query_string), fragment)

    # Convert query parameters to a dictionary, so that they can be compared correctly
    scheme, netloc, path, query_string, fragment = urlsplit(second)
    second = (scheme, netloc, path, parse_qs(query_string), fragment)

    assert first == second


def assert_url_contains_query_parameters(url, query_params):
    """
    Assert that a url string contains the given query parameters.

    Args:
        url: Full url string to check
        query_params: Dict of query string key/value pairs

    Raises:
        Assertion error if the params do not exist in the given url

    """
    query_string = urlparse(url).query
    query_string_dict = parse_qs(query_string)
    for key, value in query_params.items():
        assert key in query_string_dict and value in query_string_dict.get(key)


@mark.django_db
class APITest(APITestCase):
    """
    Base class for API Tests.
    """

    def setUp(self):
        """
        Perform operations common to all tests.
        """
        super().setUp()
        self.create_user(username=TEST_USERNAME, email=TEST_EMAIL, password=TEST_PASSWORD)
        self.client = APIClient()
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)

    def tearDown(self):
        """
        Perform common tear down operations to all tests.
        """
        # Remove client authentication credentials
        self.client.logout()
        super().tearDown()

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, **kwargs)
        self.user.set_password(password)
        self.user.save()

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

    def get_request_with_jwt_cookie(self, system_wide_role=None, context=None):
        """
        Set jwt token in cookies.
        """
        payload = generate_unversioned_payload(self.user)
        if system_wide_role:
            payload.update({
                'roles': [
                    '{system_wide_role}:{context}'.format(system_wide_role=system_wide_role, context=context)
                ]
            })
        jwt_token = generate_jwt_token(payload)

        request = RequestFactory().get('/')
        request.COOKIES[jwt_cookie_name()] = jwt_token
        return request

    def set_multiple_enterprise_roles_to_jwt(self, context_and_roles):
        """
        Sets multiple roles to the jwt token cookies
        """
        jwt_roles = []
        for pairs in context_and_roles:
            context, role = pairs
            jwt_roles.append(f"{context}:{role}")
        payload = generate_unversioned_payload(self.user)
        payload.update({
            'roles': jwt_roles
        })
        jwt_token = generate_jwt_token(payload)

        self.client.cookies[jwt_cookie_name()] = jwt_token

    def set_jwt_cookie(self, system_wide_role='enterprise_admin', context='some_context'):
        """
        Set jwt token in cookies.
        """
        role_data = '{system_wide_role}'.format(system_wide_role=system_wide_role)
        if context is not None:
            role_data += ':{context}'.format(context=context)

        payload = generate_unversioned_payload(self.user)
        payload.update({
            'roles': [role_data]
        })
        jwt_token = generate_jwt_token(payload)

        self.client.cookies[jwt_cookie_name()] = jwt_token


class MockLoggingHandler(logging.Handler):
    """
    Mock logging handler to help check for logging statements.
    """

    def __init__(self, *args, **kwargs):
        """
        Reset messages with each initialization.
        """
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        """
        Override to catch messages and store them messages in our internal dicts.
        """
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        """
        Clear out all messages, also called to initially populate messages dict.
        """
        self.messages = {
            'debug': [],
            'info': [],
            'warning': [],
            'error': [],
            'critical': [],
        }


class EnterpriseFormViewTestCase(TestCase):
    """
    Base class for TestCase.

    It has support for mocking of rendering the template file for FormView.
    """

    url = None
    template_path = None

    def setUp(self):
        """
        Mocked the rendering the template file.
        """
        super().setUp()
        # create a temporary template file
        # rendering View's template fails becuase of dependency on edx-platform
        tpl = tempfile.NamedTemporaryFile(  # pylint: disable=consider-using-with
            prefix='test_template.',
            suffix=".html",
            dir=os.path.join(settings.REPO_ROOT, 'templates/enterprise/'),
            delete=False,
        )
        tpl.close()
        self.addCleanup(os.remove, tpl.name)

        patcher = mock.patch(
            self.template_path,
            mock.PropertyMock(return_value=tpl.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)


class EmptyCacheMixin:
    """
    Mixin the clears the default cache before each test function.
    """

    def setUp(self):
        super().setUp()
        caches['default'].clear()


class ReturnValueSpy:
    """
    Helper class to be used with mock and patch so that inner commands may be inspected.
    Useful for integration tests. Example Usage with a management command:
    def test():
        with patch('low_level_class.my_m', ReturnValueSpy(goo)) as goo_mock:
            x = foo()
            x = foo()
            print(goo_mock.return_values)
            assert goo_mock.return_values == [3, 3]

    """

    def __init__(self, func):
        self.func = func
        self.return_values = []

    def __call__(self, *args, **kwargs):
        answer = self.func(*args, **kwargs)
        self.return_values.append(answer)
        return answer
