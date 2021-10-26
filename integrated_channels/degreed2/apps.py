# -*- coding: utf-8 -*-
"""
Enterprise Integrated Channel Degreed2 Django application initialization.
"""

from django.apps import AppConfig


class Degreed2Config(AppConfig):
    """
    Configuration for the Enterprise Integrated Channel Degreed2 Django application.
    """
    name = 'integrated_channels.degreed2'
    verbose_name = "Enterprise Degreed2 Integration"
    oauth_api_path = "/oauth/token"
    courses_api_path = "/api/v2/content/courses"
    completions_api_path = "/completions"
