"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.urls import include, path

urlpatterns = [
    path(
        'v1/',
        include('enterprise_learner_portal.api.v1.urls'),
        name='v1'
    )
]
