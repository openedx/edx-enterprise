"""
URL definitions for Cornerstone API.
"""

from django.urls import path

from integrated_channels.cornerstone.views import CornerstoneCoursesListView

urlpatterns = [
    path('course-list', CornerstoneCoursesListView.as_view(),
         name='cornerstone-course-list'
         )
]
