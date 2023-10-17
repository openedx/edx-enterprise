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
from django.utils.translation import gettext as _

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.api.v1.serializers import (
    EnterpriseAssignedCoursesSerializer,
    EnterpriseCourseEnrollmentSerializer,
)

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


class EnterpriseAssignedCoursesView(APIView):
    """
    View for returning information about given assigned courses.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)

    def get(self, request):
        """
        Returns details about given assigned courses.

        Example response:

        [
            {
                "course_run_id": "course-v1:edX+L153+2T2023",
                "created": "2023-08-28T13:21:55.913099Z",
                "start_date": "2023-10-19T10:46:36Z",
                "end_date": "2023-12-30T10:46:44Z",
                "display_name": "Works of Ivan Turgenev",
                "course_run_url": "http://localhost:2000/course/course-v1:edX+L153+2T2023/home",
                "course_run_status": "in_progress",
                "pacing": "instructor",
                "org_name": "edX",
                "certificate_download_url": null,
                "enroll_by": "2023-10-25T10:46:49Z",
                "course_type": "executive-education-2u",
                "product_source": "2u"
            },
            {
                "course_run_id": "course-v1:edX+P315+2T2023",
                "created": "2023-08-28T13:21:46.584659Z",
                "start_date": "2023-08-30T13:21:46Z",
                "end_date": "2023-10-17T13:21:46Z",
                "display_name": "Quantum Entanglement",
                "course_run_url": "http://localhost:2000/course/course-v1:edX+P315+2T2023/home",
                "course_run_status": "completed",
                "pacing": "instructor",
                "org_name": "edX",
                "certificate_download_url": null
            }
        ]

        Query parameters:
        - `course_ids` (List[str], required): A list of course IDs for which details are requested.
        - The `course_ids` should be URL-encoded, replacing the '+' sign with '%2B'.
        Example: course-v1:edX%2BL153%2B2T2023
        """

        if get_course_overviews is None:
            raise NotConnectedToOpenEdX(
                _('To use this endpoint, this package must be '
                  'installed in an Open edX environment.')
            )

        course_ids = request.GET.getlist('course_ids')

        if not course_ids:
            return Response(
                {'error': 'course_ids must be provided as query parameters'},
                status=HTTP_400_BAD_REQUEST
            )

        assigned_courses_overviews = get_course_overviews(course_ids)

        data = EnterpriseAssignedCoursesSerializer(
            assigned_courses_overviews,
            many=True,
            context={'request': request}
        ).data

        return Response(data)
