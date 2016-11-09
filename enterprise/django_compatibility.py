# -*- coding: utf-8 -*-
"""
Abstracts incompatibilities between Django versions.
"""
from __future__ import absolute_import, unicode_literals

# pylint: disable=unused-import
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse  # django 1.10 compatibility
