# -*- coding: utf-8 -*-
"""
URL definitions for integrated_channels API endpoint.
"""

from django.conf.urls import include, url

app_name = 'api'
urlpatterns = [
    url(r'^v1/', include('integrated_channels.api.v1.urls'), name='api')
]
