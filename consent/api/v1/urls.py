# -*- coding: utf-8 -*-
"""
URL definitions for version 1 of the Consent API.

Currently supports the following services:
    ``data_sharing_consent``: Allows for getting, providing, and revoking consent to share data.
"""

from django.conf.urls import url

from .views import DataSharingConsentView

urlpatterns = [
    url(
        r'^data_sharing_consent$',
        DataSharingConsentView.as_view(),
        name='data_sharing_consent'
    ),
]
