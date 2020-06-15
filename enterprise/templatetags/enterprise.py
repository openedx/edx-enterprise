"""
Template tags and filters for the Enterprise application.
"""

from django import template
from django.utils.safestring import mark_safe

from enterprise.utils import strip_html_tags

register = template.Library()  # pylint: disable=invalid-name

MESSAGE_ICONS = {
    'success': 'fa-check-circle',
    'info': 'fa-info-circle',
    'warning': 'fa-exclamation-triangle',
    'error': 'fa-times-circle',
}


@register.inclusion_tag('enterprise/templatetags/fa_icon.html')
def fa_icon(message_type):
    """
    Django template tag that returns font awesome icon depending upon message type.

    Usage:
        {% fa_icon "success" %}
    """
    return {
        'icon': MESSAGE_ICONS.get(message_type, 'fa-{}'.format(message_type))
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


@register.inclusion_tag('enterprise/templatetags/expand_button.html')
def expand_button(value, href):
    """
    Django template tag that returns a button used to expand/collapse a container.

    You may pass in the ID of the container that this button controls, and a button text value.

    Usage:
        {% expand_button 'Click me!' '#id' %}
    """
    return {
        'value': value,
        'href': href,
    }


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
        ' data-toggle="modal"'
        ' data-target="#course-details-modal-{index}"'
        '>{link_text}</a>'
    ).format(
        index=index,
        link_text=link_text,
    )
    return mark_safe(link)


@register.filter()
def only_safe_html(html_text):
    """
    Django template filter that strips all HTML tags excepts those degined in ALLOWED_TAGS.

    General Usage:
        {{ html_text|only_safe_html }}
    """
    return mark_safe(strip_html_tags(html_text))
