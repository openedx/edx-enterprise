# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utils module.
"""

import unittest
from unittest import mock

import ddt
from pytest import mark

from django.conf import settings

from enterprise.utils import get_idiff_list, get_platform_logo_url


@mark.django_db
@ddt.ddt
class TestGetDifferenceList(unittest.TestCase):
    """
    Tests for :method:`get_idiff_list`.
    """

    @ddt.unpack
    @ddt.data(
        (
            [],
            [],
            []
        ),
        (
            ['DUMMY1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            ['dummy1@example.com', 'DUMMY3@EXAMPLE.COM'],
            ['dummy2@example.com']
        ),
        (
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            [],
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
        )
    )
    def test_get_idiff_list_method(self, all_emails, registered_emails, unregistered_emails):
        emails = get_idiff_list(all_emails, registered_emails)
        self.assertEqual(sorted(emails), sorted(unregistered_emails))


@mark.django_db
@ddt.ddt
class TestUtils(unittest.TestCase):
    """
    Tests for utility functions in enterprise.utils
    """

    @ddt.unpack
    @ddt.data(
        (None, None),
        ('http://fake.url/logo.png', 'http://fake.url/logo.png'),
        ('./images/logo.png', '{}/images/logo.png'.format(settings.LMS_ROOT_URL)),
    )
    @mock.patch('enterprise.utils.get_logo_url')
    def test_get_platform_logo_url(self, logo_url, expected_logo_url, mock_get_logo_url):
        """
        Verify that the URL returned from get_logo_url is
        returned from get_platform_logo_url.
        """
        mock_get_logo_url.return_value = logo_url
        self.assertEqual(get_platform_logo_url(), expected_logo_url)
