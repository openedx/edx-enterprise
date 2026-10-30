"""
URLs for edX Enterprise's Consent application.
"""

from django.urls import include, path

urlpatterns = [
    path('consent/api/', include('consent.api.urls'),
         name='consent_api'
         ),
]
