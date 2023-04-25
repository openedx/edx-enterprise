"""
Tests for the `edx-enterprise` throttles module.
"""

from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from test_utils import APITest, factories


@mark.django_db
class TestEnterpriseAPIThrottling(APITest):
    """
    Tests for enterprise API throttling.
    """

    USER_THROTTLE_RATE = int(settings.USER_THROTTLE_RATE.split('/')[0])
    SERVICE_USER_THROTTLE_RATE = int(settings.SERVICE_USER_THROTTLE_RATE.split('/')[0])

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super().setUp()

        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=user.id)

        self.url = settings.TEST_SERVER + reverse('enterprise-customer-list')

    def tearDown(self):
        """
        Clears the Django cache, which means that throttle limits
        will be reset between test runs.
        """
        super().tearDown()
        cache.clear()

    def _exhaust_throttle_limit(self, throttle_limit):
        """
        Call enterprise api so that throttle limit is exhausted.
        """
        for _ in range(throttle_limit):
            response = self.client.get(self.url)
            assert response.status_code == status.HTTP_200_OK

    @override_settings(USER_THROTTLE_RATE='10/minute', SERVICE_USER_THROTTLE_RATE='15/minute')
    def _exhaust_service_worker_and_assert_429(self, username, password):
        """
        Helper that will exhaust requests of service users to the limit,
        then make one more request and assert that a ``429 Too Many Requests``
        is received as the response.
        """
        self.client.login(username=username, password=password)

        self._exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

        # Now exhaust remaining service user's throttle limit
        self._exhaust_throttle_limit(throttle_limit=self.SERVICE_USER_THROTTLE_RATE - self.USER_THROTTLE_RATE - 1)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @override_settings(ENTERPRISE_ALL_SERVICE_USERNAMES=[], USER_THROTTLE_RATE='10/minute')
    def test_user_throttle(self):
        """
        Make sure throttling works as expected for regular users.
        """
        self.create_user('test_user', 'QWERTY')
        self.client.login(username='test_user', password='QWERTY')
        self._exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @override_settings(ENTERPRISE_ALL_SERVICE_USERNAMES=['some_service_user'], USER_THROTTLE_RATE='10/minute')
    def test_user_throttle_with_service_user_list(self):
        """
        Make sure throttling works as expected for regular users when service users
        are specified by a list.
        """
        self.create_user('test_user', 'QWERTY')
        self.client.login(username='test_user', password='QWERTY')
        self._exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @override_settings(ENTERPRISE_ALL_SERVICE_USERNAMES=[])
    def test_service_user_throttle(self):
        """
        Make sure throttling is bypassed for service users.
        """
        # Create a service user and log in.
        self.create_user(settings.ENTERPRISE_SERVICE_WORKER_USERNAME, 'QWERTY')
        self._exhaust_service_worker_and_assert_429(settings.ENTERPRISE_SERVICE_WORKER_USERNAME, 'QWERTY')

    @override_settings(ENTERPRISE_ALL_SERVICE_USERNAMES=[None])
    def test_service_user_throttle_list_of_none(self):
        """
        With a list of all service users specified as ``[None]``, *every* user
        should be treated as a regular user.
        """
        self.create_user(settings.ENTERPRISE_SERVICE_WORKER_USERNAME, 'QWERTY')
        self.client.login(username=settings.ENTERPRISE_SERVICE_WORKER_USERNAME, password='QWERTY')
        self._exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_service_user_from_list_throttle(self):
        """
        Make sure service user throttling works when specifying setting as a list of usernames.
        """
        for username in settings.ENTERPRISE_ALL_SERVICE_USERNAMES:
            self.create_user(username=username, password='QWERTY')
            self._exhaust_service_worker_and_assert_429(username, 'QWERTY')
