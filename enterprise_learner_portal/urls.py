"""
URL definitions for enterprise API endpoint.
"""

from django.urls import include, path

urlpatterns = [
    path('api/', include('enterprise_learner_portal.api.urls'), name='api')
]
