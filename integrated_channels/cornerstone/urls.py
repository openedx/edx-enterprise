# -*- coding: utf-8 -*-
"""
URL definitions for Cornerstone API.
"""

from django.conf.urls import url

from integrated_channels.cornerstone.views import CornerstoneCoursesListView

urlpatterns = [
    url(
        r'^course-list$',
        CornerstoneCoursesListView.as_view(),
        name='cornerstone-course-list'
    ),
]
