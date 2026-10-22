"""
Enterprise Integrated Channel Canvas Django application initialization.
"""

from django.apps import AppConfig


class CanvasConfig(AppConfig):
    """
    Configuration for the Enterprise Integrated Channel Canvas Django application.
    """
    name = 'integrated_channels.canvas'
    verbose_name = "Enterprise Canvas Integration"
    oauth_token_auth_path = "login/oauth2/token"
