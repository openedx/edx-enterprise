"""
URL definitions for enterprise API endpoint.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url
from enterprise.api.v1.urls import router as api_v1_router

urlpatterns = [
    url(r'^v1/', include(api_v1_router.urls), name='api')
]
