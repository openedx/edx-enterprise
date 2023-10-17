"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.urls import path

from enterprise_learner_portal.api.v1.views import EnterpriseAssignedCoursesView, EnterpriseCourseEnrollmentView

urlpatterns = [
    path('enterprise_course_enrollments/', EnterpriseCourseEnrollmentView.as_view(),
         name="enterprise-learner-portal-course-enrollment-list"
         ),
    path('enterprise_assigned_courses/', EnterpriseAssignedCoursesView.as_view(),
         name="enterprise-learner-portal-assigned-courses-list"
         ),
]
