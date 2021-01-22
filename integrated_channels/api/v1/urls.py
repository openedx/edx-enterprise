# -*- coding: utf-8 -*-
"""
URL definitions for v1 Integrated Channel API endpoints.
"""

from django.conf.urls import include, url

app_name = 'v1'
urlpatterns = [
    url(r'^canvas/', include('integrated_channels.api.v1.canvas.urls')),
    url(r'^moodle/', include('integrated_channels.api.v1.moodle.urls')),
    url(r'^blackboard/', include('integrated_channels.api.v1.blackboard.urls')),
    url(r'^sap_success_factors/', include('integrated_channels.api.v1.sap_success_factors.urls')),
    url(r'^degreed/', include('integrated_channels.api.v1.degreed.urls')),
    url(r'^cornerstone/', include('integrated_channels.api.v1.cornerstone.urls'))
]
