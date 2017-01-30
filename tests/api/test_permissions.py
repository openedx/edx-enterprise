# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api permissions.
"""
from __future__ import absolute_import, unicode_literals

import ddt
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

from test_utils import TEST_PASSWORD, TEST_USERNAME, APITest


@ddt.ddt
class TestEnterpriseAPIPermissions(APITest):
    """
    Tests for enterprise api permissions.
    """

    @ddt.data(
        (TEST_USERNAME, TEST_PASSWORD, status.HTTP_200_OK),
        ('invalid_user', 'invalid_password', status.HTTP_401_UNAUTHORIZED),
    )
    @ddt.unpack
    def test_permissions(self, username, password, expected_status):
        # Destroy existing sessions
        self.client.logout()

        # Update authentication parameters based in ddt data.
        self.client.login(username=username, password=password)
        response = self.client.get(settings.TEST_SERVER + reverse('site-list'))

        assert response.status_code == expected_status
