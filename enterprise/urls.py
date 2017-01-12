# -*- coding: utf-8 -*-
"""
URLs for enterprise.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

from enterprise.views import GrantDataSharingPermissions

urlpatterns = [
    url(
        r'^enterprise/grant_data_sharing_permissions',
        GrantDataSharingPermissions.as_view(),
        name='grant_data_sharing_permissions'
    ),
    url(
        r'^enterprise/api/',
        include('enterprise.api.urls'),
        name='enterprise_api'
    )
]
