# -*- coding: utf-8 -*-
"""
URLs for enterprise.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.conf.urls import include, url

from enterprise.views import CourseEnrollmentView, GrantDataSharingPermissions, HandleConsentEnrollment


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
        HandleConsentEnrollment.as_view(),
        name='enterprise_handle_consent_enrollment'),
    url(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/course/{}/enroll/$'.format(settings.COURSE_ID_PATTERN),
        CourseEnrollmentView.as_view(),
        name='enterprise_course_enrollment_page'),
    url(
        r'^enterprise/api/',
        include('enterprise.api.urls'),
        name='enterprise_api'
    ),
]

# Because ROOT_URLCONF points here, we are including the urls from the integrated_channels app here for now.
urlpatterns += [
    url(
        r'',
        include('integrated_channels.integrated_channel.urls'),
        name='integrated_channel'
    ),
]
