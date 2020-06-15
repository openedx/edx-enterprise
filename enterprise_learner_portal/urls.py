# -*- coding: utf-8 -*-
"""
URL definitions for enterprise API endpoint.
"""

from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('enterprise_learner_portal.api.urls'), name='api')
]
