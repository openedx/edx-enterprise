"""
Enterprise xAPI Django application initialization.
"""

from django.apps import AppConfig


class XAPIConfig(AppConfig):
    """
    Configuration for the xAPI Django application.
    """
    name = 'integrated_channels.xapi'
    verbose_name = "Enterprise xAPI Integration"
