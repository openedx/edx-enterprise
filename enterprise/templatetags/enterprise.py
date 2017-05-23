"""
Template tags for enterprise apps.
"""
from __future__ import absolute_import, unicode_literals

from django import template


register = template.Library()  # pylint: disable=invalid-name

MESSAGE_ICONS = {
    'success': 'fa-check-circle',
    'info': 'fa-info-circle',
    'warning': 'fa-exclamation-circle',
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
    Django template tag that returns font awesome icon depending upon message type.

    Usage:
        {% alert_messages messages %}
    """
    return {
        'messages': messages
    }
