# -*- coding: utf-8 -*-
"""
URLs for edX Enterprise's Consent application.
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

urlpatterns = [
    url(
        r'^consent/api/',
        include('consent.api.urls'),
        name='consent_api'
    ),
]
