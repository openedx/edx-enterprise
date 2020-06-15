# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` throttles module.
"""

from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

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
        super(TestEnterpriseAPIThrottling, self).setUp()

        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=user.id)

        self.url = settings.TEST_SERVER + reverse('enterprise-customer-list')

    def exhaust_throttle_limit(self, throttle_limit):
        """
        Call enterprise api so that throttle limit is exhausted.
        """
        for item in range(throttle_limit):  # pylint: disable=unused-variable
            response = self.client.get(self.url)
            assert response.status_code == status.HTTP_200_OK

    def test_user_throttle(self):
        """
        Make sure throttling works as expected for regular users.
        """
        self.create_user('test_user', 'QWERTY')
        self.client.login(username='test_user', password='QWERTY')
        self.exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_service_user_throttle(self):
        """
        Make sure throttling is bypassed for service users.
        """
        # Create a service user and log in.
        self.create_user(settings.ENTERPRISE_SERVICE_WORKER_USERNAME, 'QWERTY')
        self.client.login(username=settings.ENTERPRISE_SERVICE_WORKER_USERNAME, password='QWERTY')

        self.exhaust_throttle_limit(throttle_limit=self.USER_THROTTLE_RATE)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

        # Now exhaust remaining service user's throttle limit
        self.exhaust_throttle_limit(throttle_limit=(self.SERVICE_USER_THROTTLE_RATE - self.USER_THROTTLE_RATE - 1))
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
