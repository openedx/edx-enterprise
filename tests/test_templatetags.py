"""
Tests for django template tags.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt

from django.contrib import messages
from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.template import Context, Template
from django.test import RequestFactory


@ddt.ddt
class EnterpriseTemplateTagsTest(unittest.TestCase):
    """
    Tests for enterprise template tags.
    """

    @staticmethod
    def _add_messages(request, alert_messages):
        """
        Add django messages to the request context using `messages` app.

        Arguments:
            alert_messages (list): A list of tuples containing message type and message body.
                e.g. [('success', 'This is a dummy success message.'), ]
        """
        for message_type, message in alert_messages:
            messages.add_message(request, message_type, message)

    @staticmethod
    def _get_mock_request():
        """
        Get mock django HttpRequest object.
        """
        request = RequestFactory().get('/')
        request.session = cache.SessionStore()
        # Monkey-patch storage for messaging;   pylint: disable=protected-access
        request._messages = fallback.FallbackStorage(request)

        return request

    @ddt.data(
        ('success', '<i class="fa fa-check-circle" aria-hidden="true"></i>'),
        ('info', '<i class="fa fa-info-circle" aria-hidden="true"></i>'),
        ('warning', '<i class="fa fa-exclamation-triangle" aria-hidden="true"></i>'),
        ('error', '<i class="fa fa-times-circle" aria-hidden="true"></i>'),
        ('unknown-status-tag', ''),
    )
    @ddt.unpack
    def test_fa_icon(self, message_type, expected_favicon):
        """
        Test that fa_icon template tag returns correct favicon for status tag.
        """
        template = Template("{% load enterprise %} {% fa_icon '" + message_type + "' %}")
        rendered = template.render(Context({}))

        assert expected_favicon == rendered.strip()

    @ddt.data(
        (
            [
                (messages.INFO, 'This is a dummy info message.'),
            ],
            [
                ('<i class="fa fa-info-circle" aria-hidden="true"></i>', 'This is a dummy info message.'),
            ],
        ),
        (
            [
                (messages.SUCCESS, 'This is a dummy success message.'),
                (messages.INFO, 'This is a dummy info message.'),
            ],
            [
                ('<i class="fa fa-check-circle" aria-hidden="true"></i>', 'This is a dummy success message.'),
                ('<i class="fa fa-info-circle" aria-hidden="true"></i>', 'This is a dummy info message.'),
            ],
        ),
        (
            [
                (messages.SUCCESS, 'This is a dummy success message.'),
                (messages.ERROR, 'This is a dummy error message.'),
                (messages.INFO, 'This is a dummy info message.'),
                (messages.WARNING, 'This is a dummy warning message.'),
            ],
            [
                ('<i class="fa fa-check-circle" aria-hidden="true"></i>', 'This is a dummy success message.'),
                ('<i class="fa fa-times-circle" aria-hidden="true"></i>', 'This is a dummy error message.'),
                ('<i class="fa fa-info-circle" aria-hidden="true"></i>', 'This is a dummy info message.'),
                ('<i class="fa fa-exclamation-triangle" aria-hidden="true"></i>', 'This is a dummy warning message.'),
            ],
        ),
    )
    @ddt.unpack
    def test_alert_messages(self, alert_messages, expected_messages):
        """
        Test that fa_icon template tag returns correct favicon for status tag.
        """
        request = self._get_mock_request()
        self._add_messages(request, alert_messages)

        template = Template("{% load enterprise %} {% alert_messages messages %}")
        rendered = template.render(Context({'messages': messages.get_messages(request)}))

        for expected_icon, expected_message in expected_messages:
            assert expected_icon in rendered.strip()
            assert expected_message in rendered.strip()
