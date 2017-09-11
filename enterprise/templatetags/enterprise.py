"""
Template tags and filters for the Enterprise application.
"""
from __future__ import absolute_import, unicode_literals

from django import template
from django.utils.safestring import mark_safe

register = template.Library()  # pylint: disable=invalid-name

MESSAGE_ICONS = {
    'success': 'fa-check-circle',
    'info': 'fa-info-circle',
    'warning': 'fa-exclamation-triangle',
    'error': 'fa-times-circle'
}


@register.inclusion_tag('enterprise/templatetags/fa_icon.html')
def fa_icon(message_type):
    """
    Django template tag that returns font awesome icon depending upon message type.

    Usage:
        {% fa_icon "success" %}
    """
    return {
        'icon': MESSAGE_ICONS.get(message_type)
    }


@register.inclusion_tag('enterprise/templatetags/alert_messages.html')
def alert_messages(messages):
    """
    Django template tag that returns an alert message.

    Usage:
        {% alert_messages messages %}
    """
    return {
        'messages': messages
    }


@register.inclusion_tag('enterprise/templatetags/course_modal.html', takes_context=True)
def course_modal(context, course=None):
    """
    Django template tag that returns course information to display in a modal.

    You may pass in a particular course if you like. Otherwise, the modal will look for course context
    within the parent context.

    Usage:
        {% course_modal %}
        {% course_modal course %}
    """
    if course:
        context.update({
            'course_image_uri': course.get('course_image_uri', ''),
            'course_title': course.get('course_title', ''),
            'course_level_type': course.get('course_level_type', ''),
            'course_short_description': course.get('course_short_description', ''),
            'course_effort': course.get('course_effort', ''),
            'course_full_description': course.get('course_full_description', ''),
            'expected_learning_items': course.get('expected_learning_items', []),
            'staff': course.get('staff', []),
            'premium_modes': course.get('premium_modes', []),
        })
    return context


@register.filter(needs_autoescape=True)
def link_to_modal(link_text, index, autoescape=True):  # pylint: disable=unused-argument
    """
    Django template filter that returns an anchor with attributes useful for course modal selection.

    General Usage:
        {{ link_text|link_to_modal:index }}

    Examples:
        {{ course_title|link_to_modal:forloop.counter0 }}
        {{ course_title|link_to_modal:3 }}
        {{ view_details_text|link_to_modal:0 }}
    """
    link = (
        '<a'
        ' href="#!"'
        ' class="text-underline view-course-details-link"'
        ' id="view-course-details-link-{index}"'
        '>{link_text}</a>'
    ).format(
        index=index,
        link_text=link_text,
    )
    return mark_safe(link)
