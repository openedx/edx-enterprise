# -*- coding: utf-8 -*-
"""
Test mixins for enterprise tests.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import messages


class MessagesMixin(object):
    """
    Mixin for testing expected Django messages.
    """

    def _get_messages_from_response_cookies(self, response):
        """
        Get django messages set in response cookies.
        """
        # pylint: disable=protected-access
        try:
            return messages.storage.cookie.CookieStorage(response)._decode(response.cookies['messages'].value)
        except KeyError:
            # No messages stored in cookies
            return None

    def _assert_request_message(self, request_message, expected_message_tags, expected_message_text):
        """
        Verify the request message tags and text.
        """
        self.assertEqual(request_message.tags, expected_message_tags)
        self.assertEqual(request_message.message, expected_message_text)

    def _assert_django_test_client_messages(self, test_client_response, expected_log_messages):
        """
        Verify that expected messages are included in the context of response.
        """
        response_messages = [
            (msg.level, msg.message) for msg in test_client_response.context['messages']  # pylint: disable=no-member
        ]
        assert response_messages == expected_log_messages


class ConsentMixin(object):
    """
    Mixin for testing expectations related to consents.
    """

    def _assert_consent_provided(self, response):
        """Assert consent is provided."""
        self.assertTrue(response.data.get('consent_provided'))

    def _assert_consent_not_provided(self, response):
        """Assert that consent is not provided."""
        with self.assertRaises(Exception):
            self._assert_consent_provided(response)

    def _assert_consent_required(self, response):
        """Assert consent is required."""
        self.assertTrue(response.data.get('consent_required'))

    def _assert_consent_not_required(self, response):
        """Assert consent is not required."""
        with self.assertRaises(Exception):
            self._assert_consent_required(response)
