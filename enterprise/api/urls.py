# -*- coding: utf-8 -*-
"""
URL definitions for enterprise API endpoint.
"""

from django.conf.urls import include, url

urlpatterns = [
    url(r'^v1/', include('enterprise.api.v1.urls'), name='api')
]
