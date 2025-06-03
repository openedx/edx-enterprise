"""
URL definitions for enterprise API endpoint.
"""

from django.urls import include, path

urlpatterns = [
    path('v1/', include('enterprise.api.v1.urls'), name='api')
]
