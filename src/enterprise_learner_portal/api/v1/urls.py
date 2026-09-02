"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.urls import path

from enterprise_learner_portal.api.v1.views import EnterpriseCourseEnrollmentView

urlpatterns = [
    path('enterprise_course_enrollments/', EnterpriseCourseEnrollmentView.as_view(),
         name="enterprise-learner-portal-course-enrollment-list"
         ),
]
