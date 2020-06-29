# -*- coding: utf-8 -*-
"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.conf.urls import url

from enterprise_learner_portal.api.v1.views import EnterpriseCourseEnrollmentView

urlpatterns = [
    url(
        r'^enterprise_course_enrollments/$',
        EnterpriseCourseEnrollmentView.as_view(),
        name="enterprise-learner-portal-course-enrollment-list"
    ),
]
