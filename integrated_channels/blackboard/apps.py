# -*- coding: utf-8 -*-
"""
Enterprise Integrated Channel Blackboard Django application initialization.
"""

from django.apps import AppConfig

CHANNEL_NAME = 'integrated_channels.blackboard'
VERBOSE_NAME = 'Enterprise Blackboard Integration'


class BlackboardConfig(AppConfig):
    """
    Configuration for the Enterprise Integrated Channel Blackboard Django application.
    """
    name = CHANNEL_NAME
    verbose_name = VERBOSE_NAME
