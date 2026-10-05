"""
URL definitions for version 1 of the Consent API.

Currently supports the following services:
    ``data_sharing_consent``: Allows for getting, providing, and revoking consent to share data.
"""

from django.urls import path

from .views import DataSharingConsentView

urlpatterns = [
    path('data_sharing_consent', DataSharingConsentView.as_view(),
         name='data_sharing_consent'
         ),
]
