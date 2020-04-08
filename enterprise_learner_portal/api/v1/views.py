# -*- coding: utf-8 -*-
"""
Views for enterprise_learner_portal app.
"""
from __future__ import absolute_import, unicode_literals

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
        Get method for the view.
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

        course_overviews = get_course_overviews(enterprise_enrollments.values_list('course_id', flat=True))

        data = EnterpriseCourseEnrollmentSerializer(
            enterprise_enrollments,
            many=True,
            context={'request': request, 'course_overviews': course_overviews},
        ).data

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
        marked_done = request.query_params.get('marked_done', None)
        if not enterprise_customer_id or not course_id or marked_done is None:
            return Response(
                {'error': 'enterprise_id, course_id, and marked_done must be provided as query parameters'},
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

        enterprise_enrollment.marked_done = marked_done
        enterprise_enrollment.save()

        course_overviews = get_course_overviews([course_id])
        data = EnterpriseCourseEnrollmentSerializer(
            enterprise_enrollment,
            context={'request': request, 'course_overviews': course_overviews},
        ).data

        return Response(data)
