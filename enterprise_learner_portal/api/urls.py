# -*- coding: utf-8 -*-
"""
URL definitions for enterprise_learner_portal API endpoint.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

urlpatterns = [
    url(r'^v1/', include('enterprise_learner_portal.api.v1.urls'), name='v1')
]
