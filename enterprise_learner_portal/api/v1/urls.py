# -*- coding: utf-8 -*-
"""
URL definitions for enterprise_learner_portal API endpoint.
"""

from django.conf.urls import url

from enterprise_learner_portal.api.v1 import views

urlpatterns = [
    url(
        r'^enterprise_course_enrollments/$',
        views.EnterpriseCourseEnrollmentView.as_view(),
        name="enterprise-learner-portal-course-enrollment-list",
    ),
    url(
        r'^enterprise_customer_user/$',
        views.EnterpriseCustomerUserView.as_view(),
        name="enterprise-learner-portal-enterprise-learner-detail",
    ),
]
