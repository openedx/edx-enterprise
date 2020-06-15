# -*- coding: utf-8 -*-
"""
URL definitions for edX Enterprise's Consent API endpoint.
"""

from django.conf.urls import include, url

urlpatterns = [
    url(
        r'^v1/',
        include('consent.api.v1.urls'),
        name='consent_api_v1'
    ),
]
