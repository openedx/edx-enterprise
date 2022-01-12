"""
Tests for django template tags.
"""

import unittest

import ddt

from django.contrib import messages
from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.template import Context, Template
from django.test import RequestFactory

from test_utils.fake_catalog_api import FAKE_COURSE_RUN


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
        ('plus-circle', '<i class="fa fa-plus-circle" aria-hidden="true"></i>'),
        ('minus-circle', '<i class="fa fa-minus-circle" aria-hidden="true"></i>'),
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
        Test that the alert_messages template tag returns the correct message given a message type.
        """
        request = self._get_mock_request()
        self._add_messages(request, alert_messages)

        template = Template("{% load enterprise %} {% alert_messages messages %}")
        rendered = template.render(Context({'messages': messages.get_messages(request)}))

        for expected_icon, expected_message in expected_messages:
            assert expected_icon in rendered.strip()
            assert expected_message in rendered.strip()

    @ddt.data(
        (
            {
                'premium_modes': [
                    {
                        'final_price': '$50',
                        'original_price': '$100',
                        'premium': True,
                    },
                ],
                'course_level_type': 'Type 1',
                'course_effort': '3 hours per week',
                'course_duration': '3 weeks Starting on February 05, 2013 and ending at March 05, 2014',
                'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                'expected_learning_items': ['XBlocks', 'Cool stuff'],
                'staff': FAKE_COURSE_RUN['staff'],
                'organization_name': 'organization_name',
                'organization_logo': 'organization_logo',
                'price_text': 'price_text',
                'level_text': 'level_text',
                'effort_text': 'effort_text',
                'duration_text': 'duration_text',
                'staff_text': 'staff_text',
                'close_modal_button_text': 'close_modal_button_text',
                'course_full_description_text': 'course_full_description_text',
                'expected_learning_items_text': 'expected_learning_items_text',
                'index': 0,
            },
            [
                '<button type="button" class="close" data-dismiss="modal" '
                'aria-hidden="true" aria-label="close_modal_button_text">',
                '<i class="fa fa-times" aria-hidden="true"></i>',
                '</button>',
                '<img src="organization_logo" alt="organization_name" />',
                '<span class="title">price_text</span>',
                '<span class="title">level_text</span>',
                '<span class="title">effort_text</span>',
                '<span class="title">duration_text</span>',
                '<h2 class="h3">course_full_description_text</h2>',
                '<h2 class="h3">expected_learning_items_text</h2>',
                '<h2 class="h3">staff_text</h2>',
            ]
        ),
    )
    @ddt.unpack
    def test_course_modal(self, context, expected_modal_contents):
        """
        The course_modal template tag returns the correct modal contents (not testing course-specific context).
        """
        template = Template("{% load enterprise %} {% course_modal %}")
        rendered = template.render(Context(context))
        for content in expected_modal_contents:
            assert content in rendered.strip()

    @ddt.data(
        (
            {
                'course_image_uri': 'http://edx.devstack.lms:18000/images_course_image.jpg',
                'course_title': 'edX Demonstration Course',
                'course_level_type': 'Type 1',
                'course_short_description': 'This course demonstrates many features of the edX platform.',
                'course_effort': '3 hours per week',
                'course_full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                'expected_learning_items': ['XBlocks', 'Cool stuff'],
                'staff': FAKE_COURSE_RUN['staff'],
                'premium_modes': [
                    {
                        'description': 'Earn a verified certificate!',
                        'final_price': '$50',
                        'min_price': 100,
                        'mode': 'professional',
                        'original_price': '$100',
                        'premium': True,
                        'sku': 'sku-professional',
                        'title': 'Professional Track'
                    },
                ],
            },
            [
                '<img src="http://edx.devstack.lms:18000/images_course_image.jpg" alt="edX Demonstration Course"/>',
                '<h1 id="modal-header-text-0" class="modal-header-text">edX Demonstration Course</h1>',
                '<p class="short-description">This course demonstrates many features of the edX platform.</p>',
                '<strike>$100</strike>',
                '<span class="discount">$50</span>',
                '<span class="text">Type 1</span>',
                '<span class="text">3 hours per week</span>',
                '<div>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</div>',
                '<li>XBlocks</li>', '<li>Cool stuff</li>',
                '<img src="https://www.edx.org/sites/default/files/executive/photo/anant-agarwal.jpg" '
                'alt="Anant Agarwal" />',
                '<h3 class="h4">Anant Agarwal</h3>',
                '<p>CEO at edX</p>',
                '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>',
            ],
        )
    )
    @ddt.unpack
    def test_course_modal_with_course(self, course, expected_modal_contents):
        """
        The course_modal template tag returns the correct course modal contents given a specific course.
        """
        template = Template("{% load enterprise %} {% course_modal course %}")
        rendered = template.render(Context({'course': course, 'index': 0}))
        for content in expected_modal_contents:
            assert content in rendered.strip()

    @ddt.data(
        (
            'Click me!',
            '#getmeoutofhere',
            [
                '<div class="expand-list-link-container">',
                '<form action="#getmeoutofhere" class="expand-list-link">',
                '<button type="submit" aria-controls="#getmeoutofhere" aria-expanded="false">',
                '<i class="fa fa-plus-circle" aria-hidden="true"></i>',
                '<span class="text-underline">Click me!</span>',
                ''
            ]
        ),
    )
    @ddt.unpack
    def test_expand_button(self, value, href, expected_contents):
        """
        The expand button template tag returns the correct template for buttons used to expand content.
        """
        template = Template("{% load enterprise %} {% expand_button value href %}")
        rendered = template.render(Context({'value': value, 'href': href}))
        for content in expected_contents:
            assert content in rendered.strip()


@ddt.ddt
class EnterpriseTemplateFiltersTest(unittest.TestCase):
    """
    Tests for enterprise template filters.
    """

    @ddt.data(
        '<a',
        'href="#!"',
        'text-underline',
        'view-course-details-link-0',
        'data-toggle="modal"',
        'data-target="#course-details-modal-0"',
        'edX Demonstration Course',
        '</a>'
    )
    def test_link_to_modal(self, expected_content):
        """
        The ``link_to_modal`` template filter returns the correct anchor text.
        """
        template = Template("{% load enterprise %} {{ course_title|link_to_modal:0 }}")
        rendered = template.render(Context({'course_title': 'edX Demonstration Course'}))
        assert expected_content in rendered.strip()

    @ddt.data(
        ('<a href="http://example.com" target="_blank">Link</a>', '<a href="http://example.com">Link</a>'),
        ('Strip script tag<script src="http://example.com/a.js"></script>', 'Strip script tag'),
        ('Strip link tag<link href="http://example.com/a.css" />', 'Strip link tag'),
        ('Strip iframe tag<iframe src="http://example.com"></iframe>', 'Strip iframe tag'),
        ('Strip embed tag<embed src="example.swf">', 'Strip embed tag'),
    )
    @ddt.unpack
    def test_only_safe_html(self, html, safe_html):
        """
        Test ``only_safe_html`` template filter.
        """
        template = Template("{% load enterprise %} {{ html_text|only_safe_html }}")
        rendered = template.render(Context({'html_text': html}))
        assert safe_html in rendered.strip()
