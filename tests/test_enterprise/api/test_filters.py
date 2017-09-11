# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` filters module.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from django.conf import settings

from test_utils import TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, APITest, factories


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerUserFilterBackend(APITest):
    """
    Tests for enterprise API throttling.
    """

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, **kwargs)
        self.user.set_password(password)  # pylint: disable=no-member
        self.user.save()  # pylint: disable=no-member

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        self.create_user(email=TEST_EMAIL, id=1)
        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=self.user.id)
        self.url = settings.TEST_SERVER + reverse('enterprise-learner-list')
        self.client = APIClient()
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)

    @ddt.data(
        (TEST_USERNAME, TEST_EMAIL, 1),
        (TEST_USERNAME, '', 1),
        ('', TEST_EMAIL, 1),
        ('', '', 1),
        ('dummy', '', 0),
        ('dummy', 'dummy@example.com', 0),
        ('', 'dummy@example.com', 0),
    )
    @ddt.unpack
    def test_email_filter(self, username, email, expected_data_length):
        """
        Make sure throttling works as expected for regular users.
        """

        response = self.client.get(self.url + "?email=" + email + "&username=" + username)
        assert response.status_code == status.HTTP_200_OK
        data = self.load_json(response.content)

        assert len(data['results']) == expected_data_length
