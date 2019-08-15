# -*- coding: utf-8 -*-
"""
URL definitions for enterprise API endpoint.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('enterprise_learner_portal.api.urls'), name='api')
]
