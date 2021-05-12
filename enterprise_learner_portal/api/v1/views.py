# -*- coding: utf-8 -*-
"""
Views for enterprise_learner_portal app.
"""

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.api.v1.serializers import EnterpriseCourseEnrollmentSerializer

try:
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overviews
except ImportError:
    get_course_overviews = None


class EnterpriseCourseEnrollmentView(APIView):
    """
    View for returning information around a user's enterprise course enrollments.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)

    def get(self, request):
        """
        Returns a list of EnterpriseCourseEnrollment data related to the requesting user.

        Example response:

        [
            {
                "certificate_download_url": null,
                "course_run_id": "course-v1:edX+DemoX+Demo_Course",
                "course_run_status": "in_progress",
                "start_date": "2013-02-05T06:00:00Z",
                "end_date": null,
                "display_name": "edX Demonstration Course",
                "course_run_url": "http://localhost:18000/courses/course-v1:edX+DemoX+Demo_Course/course/",
                "due_dates": [],
                "pacing": "instructor",
                "org_name": "edX",
                "is_revoked": false,
                "is_enrollment_active": true
            }
        ]

        Query params:
          'enterprise_id' (UUID string, required): The enterprise customer UUID with which to filter
            EnterpriseCustomerRecords by.
          'is_active' (boolean string, optional): If provided, will filter the resulting list of enterprise
            enrollment records to only those for which the corresponding ``student.CourseEnrollment``
            record has an ``is_active`` equal to the provided boolean value ('true' or 'false').
        """
        if get_course_overviews is None:
            raise NotConnectedToOpenEdX(
                _('To use this endpoint, this package must be '
                  'installed in an Open edX environment.')
            )

        user = request.user
        enterprise_customer_id = request.query_params.get('enterprise_id', None)
        if not enterprise_customer_id:
            return Response(
                {'error': 'enterprise_id must be provided as a query parameter'},
                status=HTTP_400_BAD_REQUEST
            )

        enterprise_customer_user = get_object_or_404(
            EnterpriseCustomerUser,
            user_id=user.id,
            enterprise_customer__uuid=enterprise_customer_id,
        )
        enterprise_enrollments = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user
        )

        filtered_enterprise_enrollments = [record for record in enterprise_enrollments if record.course_enrollment]

        course_overviews = get_course_overviews([record.course_id for record in filtered_enterprise_enrollments])

        data = EnterpriseCourseEnrollmentSerializer(
            filtered_enterprise_enrollments,
            many=True,
            context={'request': request, 'course_overviews': course_overviews},
        ).data

        if request.query_params.get('is_active'):
            is_active_filter_value = None
            if request.query_params['is_active'].lower() == 'true':
                is_active_filter_value = True
            if request.query_params['is_active'].lower() == 'false':
                is_active_filter_value = False
            if is_active_filter_value is not None:
                data = [
                    record for record in data
                    if record['is_enrollment_active'] == is_active_filter_value
                ]

        return Response(data)

    def patch(self, request):
        """
        Patch method for the view.
        """
        if get_course_overviews is None:
            raise NotConnectedToOpenEdX(
                _('To use this endpoint, this package must be '
                  'installed in an Open edX environment.')
            )

        user = request.user
        enterprise_customer_id = request.query_params.get('enterprise_id', None)
        course_id = request.query_params.get('course_id', None)
        saved_for_later = request.query_params.get('saved_for_later', None)

        if not enterprise_customer_id or not course_id or saved_for_later is None:
            return Response(
                {'error': 'enterprise_id, course_id, and saved_for_later must be provided as query parameters'},
                status=HTTP_400_BAD_REQUEST
            )

        enterprise_customer_user = get_object_or_404(
            EnterpriseCustomerUser,
            user_id=user.id,
            enterprise_customer__uuid=enterprise_customer_id,
        )

        enterprise_enrollment = get_object_or_404(
            EnterpriseCourseEnrollment,
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id
        )

        # TODO: For now, this makes the change backward compatible, we will change this to true boolean support
        enterprise_enrollment.saved_for_later = saved_for_later.lower() == 'true'

        enterprise_enrollment.save()

        course_overviews = get_course_overviews([course_id])
        data = EnterpriseCourseEnrollmentSerializer(
            enterprise_enrollment,
            context={'request': request, 'course_overviews': course_overviews},
        ).data

        return Response(data)
