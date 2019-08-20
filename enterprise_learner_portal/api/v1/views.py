# -*- coding: utf-8 -*-
"""
Views for enterprise_learner_portal app.
"""
from __future__ import absolute_import, unicode_literals

from edx_rest_framework_extensions.auth.bearer.authentication import BearerAuthentication
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
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
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)

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
        enterprise_customer_user = get_object_or_404(
            EnterpriseCustomerUser,
            user_id=user.id
        )
        course_ids_for_ent_enrollments = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user
        ).values_list('course_id', flat=True)

        overviews = get_course_overviews(course_ids_for_ent_enrollments)

        data = EnterpriseCourseEnrollmentSerializer(
            overviews,
            many=True,
            context={'request': request},
        ).data

        return Response(data)
