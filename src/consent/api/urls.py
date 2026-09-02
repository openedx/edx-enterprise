"""
URL definitions for edX Enterprise's Consent API endpoint.
"""

from django.urls import include, path

urlpatterns = [
    path('v1/', include('consent.api.v1.urls'),
         name='consent_api_v1'
         ),
]
