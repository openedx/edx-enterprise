# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utils module.
"""

import unittest
from unittest import mock

import ddt
from pytest import mark

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


class TestUtils(unittest.TestCase):
    """
    Tests for utility functions in enterprise.utils
    """

    @mock.patch('enterprise.utils.get_logo_url')
    def test_get_platform_logo_url(self, mock_get_logo_url):
        """
        Verify that the URL returned from get_logo_url is
        returned from get_platform_logo_url.
        """
        fake_url = 'http://logo.url'
        mock_get_logo_url.return_value = fake_url
        self.assertEqual(get_platform_logo_url(), fake_url)
