# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` filters module.
"""

from __future__ import absolute_import, unicode_literals

import ddt

from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

from test_utils import APITest, factories


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerUserFilterBackend(APITest):
    """
    Tests for enterprise API throttling.
    """
    username = 'test_user'
    email = 'test_user@example.com'

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super(TestEnterpriseCustomerUserFilterBackend, self).setUp()
        self.test_user = factories.UserFactory(username=self.username, email=self.email, is_active=True)

        enterprise_customer = factories.EnterpriseCustomerFactory()
        factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=self.test_user.id)

        self.url = settings.TEST_SERVER + reverse('enterprise-learner-list')

    @ddt.data(
        (username, email, 1),
        (username, '', 1),
        ('', email, 1),
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
