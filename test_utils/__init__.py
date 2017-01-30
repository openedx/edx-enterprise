"""
Test utilities.
"""
# Since py.test discourages putting __init__.py into test directory (i.e. making tests a package)
# one cannot import from anywhere under tests folder. However, some utility classes/methods might be useful
# in multiple test modules. So this package the place to put them.

from __future__ import absolute_import, unicode_literals

import json
from pytest import mark

from rest_framework.test import APITestCase, APIClient

from test_utils import factories

TEST_USERNAME = 'api_worker'
TEST_PASSWORD = 'QWERTY'


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

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True)
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
