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
