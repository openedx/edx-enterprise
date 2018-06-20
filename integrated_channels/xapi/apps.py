# -*- coding: utf-8 -*-
"""
Enterprise xAPI Django application initialization.
"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class XAPIConfig(AppConfig):
    """
    Configuration for the xAPI Django application.
    """
    name = 'integrated_channels.xapi'
    verbose_name = "Enterprise xAPI Integration"
