# -*- coding: utf-8 -*-
"""
URL definitions for Cornerstone API.
"""

from django.conf.urls import url

from integrated_channels.cornerstone.views import CornerstoneCoursesListView, CornerstoneCoursesUpdates

urlpatterns = [
    url(
        r'^course-list$',
        CornerstoneCoursesListView.as_view(),
        name='cornerstone-course-list'
    ),
    url(
        r'course-updates',
        CornerstoneCoursesUpdates.as_view(),
        name='cornerstone-course-updates'
    )
]
