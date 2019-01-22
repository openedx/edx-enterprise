# -*- coding: utf-8 -*-
"""
URLs for enterprise.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.conf.urls import include, url

from enterprise.constants import COURSE_KEY_URL_PATTERN
from enterprise.views import GrantDataSharingPermissions, RouterView

ENTERPRISE_ROUTER = RouterView.as_view()

urlpatterns = [
    url(
        r'^enterprise/grant_data_sharing_permissions',
        GrantDataSharingPermissions.as_view(),
        name='grant_data_sharing_permissions'
    ),
    url(
        r'^enterprise/handle_consent_enrollment/(?P<enterprise_uuid>[^/]+)/course/{}/$'.format(
            settings.COURSE_ID_PATTERN
        ),
        ENTERPRISE_ROUTER,
        name='enterprise_handle_consent_enrollment'
    ),
    url(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/course/{}/enroll/$'.format(COURSE_KEY_URL_PATTERN),
        ENTERPRISE_ROUTER,
        name='enterprise_course_enrollment_page'
    ),
    url(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/course/{}/enroll/$'.format(settings.COURSE_ID_PATTERN),
        ENTERPRISE_ROUTER,
        name='enterprise_course_run_enrollment_page'
    ),
    url(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/program/(?P<program_uuid>[^/]+)/enroll/$',
        ENTERPRISE_ROUTER,
        name='enterprise_program_enrollment_page'
    ),
    url(
        r'^enterprise/api/',
        include('enterprise.api.urls'),
        name='enterprise_api'
    ),
]

# Because ROOT_URLCONF points here, we are including the urls from the other apps here for now.
urlpatterns += [
    url(
        r'',
        include('consent.urls'),
        name='consent'
    ),
]
