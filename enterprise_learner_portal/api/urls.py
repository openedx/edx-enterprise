"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.conf.urls import include
from django.urls import path

urlpatterns = [
    path('v1/', include('enterprise_learner_portal.api.v1.urls'), name='v1')
]
