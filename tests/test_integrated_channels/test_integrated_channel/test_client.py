# -*- coding: utf-8 -*-
"""
Tests for the base integrated channel API client.
"""

from __future__ import absolute_import, unicode_literals

import unittest

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


class TestIntegratedChannelApiClient(unittest.TestCase):
    """
    Tests for the base ``TestIntegratedChannelApiClient`` class.
    """

    def test_missing_config(self):
        """
        Initiating an API client without an Enterprise Configuration raises ``ValueError``.
        """
        with self.assertRaises(ValueError):
            IntegratedChannelApiClient(None)

    def test_create_course_completion(self):
        """
        The ``create_course_completion`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').create_course_completion('fake-user', 'fake-payload')

    def test_delete_course_completion(self):
        """
        The ``delete_course_completion`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').delete_course_completion('fake-user', 'fake-payload')

    def test_create_course_content(self):
        """
        The ``create_course_content`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').create_course_content('fake-payload')

    def test_delete_course_content(self):
        """
        The ``delete_course_content`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').delete_course_content('fake-payload')
