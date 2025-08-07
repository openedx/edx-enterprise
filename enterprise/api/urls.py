"""
URL definitions for enterprise API endpoint.
"""

from django.urls import include, re_path

urlpatterns = [
    re_path(r'^v1/', include('enterprise.api.v1.urls'), name='api')
]
