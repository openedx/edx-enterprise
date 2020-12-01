# -*- coding: utf-8 -*-
"""
Tests for the base integrated channel API client.
"""

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

    def test_create_content_metadata(self):
        """
        The ``create_content_metadata`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').create_content_metadata('fake-payload')

    def test_update_content_metadata(self):
        """
        The ``update_content_metadata`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').update_content_metadata('fake-payload')

    def test_delete_content_metadata(self):
        """
        The ``delete_content_metadata`` method isn't implemented at the base, and should raise ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').delete_content_metadata('fake-payload')

    def test_create_assessment_reporting(self):
        """
        The ``create_assessment_reporting`` method isn't implemented at the base, and should raise
        ``NotImplementedError``.
        """
        with self.assertRaises(NotImplementedError):
            IntegratedChannelApiClient('fake-config').create_assessment_reporting('fake-user', 'fake-payload')
