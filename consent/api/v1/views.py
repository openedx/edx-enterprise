# -*- coding: utf-8 -*-
"""
A generic API for edX Enterprise's Consent application.
"""

from __future__ import absolute_import, unicode_literals

from consent.api import permissions
from consent.errors import ConsentAPIRequestError
from consent.helpers import (
    consent_exists,
    consent_provided,
    consent_required,
    get_enterprise_customer,
    get_enterprise_customer_user,
    get_user_id,
)
from edx_rest_framework_extensions.authentication import BearerAuthentication, JwtAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.views import APIView

from enterprise.api.throttles import ServiceUserThrottle
# Will be using internal models at a later time.
from enterprise.models import EnterpriseCourseEnrollment


class DataSharingConsentView(APIView):
    """
        **Use Cases**

            Presents a generic data sharing consent API to applications
            that have Enterprise customers who require data sharing
            consent from users.

        **Behavior**

            Implements GET, POST, and DELETE which each have roughly
            the following behavior (see their individual handlers for
            more documentation):

            GET /consent/api/v1/data_sharing_consent?username=bob&enterprise_customer_uuid=ENTERPRISE-UUID&course_id=ID
            >>> {
            >>>     "username": "bob",
            >>>     "course_id": "course-v1:edX+DemoX+Demo_Course",
            >>>     "enterprise_customer_uuid": "enterprise-uuid-goes-right-here",
            >>>     "exists": False,
            >>>     "consent_provided": False,
            >>>     "consent_required": True,
            >>> }

            If the ``exists`` key is false, then the body will be returned
            with a 404 Not Found error code; otherwise, 200 OK. If either
            of ``enterprise_customer_uuid`` or ``username`` is not provided, an
            appropriate 400-series error will be returned.

            POST or DELETE /consent/api/v1/data_sharing_consent
            >>> {
            >>>     "username": "bob",
            >>>     "course_id": "course-v1:edX+DemoX+Demo_Course",
            >>>     "enterprise_customer_uuid": "enterprise-uuid-goes-right-here"
            >>> }

            The API accepts JSON objects with these key-value pairs for
            POST or DELETE.

        **Notes**

            ``course_id`` specifies a course key (course-v1:edX+DemoX),
            and not a course run key (course-v1:edX+DemoX+Demo_Course).

    """

    permission_classes = (permissions.IsStaffOrUserInRequest,)
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_USERNAME = 'username'
    REQUIRED_PARAM_COURSE_ID = 'course_id'
    REQUIRED_PARAM_ENTERPRISE_CUSTOMER = 'enterprise_customer_uuid'  # pylint: disable=invalid-name

    CONSENT_EXISTS = 'exists'
    CONSENT_GRANTED = 'consent_provided'
    CONSENT_REQUIRED = 'consent_required'

    MISSING_REQUIRED_PARAMS_MSG = (
        "Query parameters incomplete: "
        "username '{username}', "
        "course_id '{course_id}', "
        "enterprise customer uuid '{enterprise_customer_uuid}'."
    )

    def get_required_query_params(self, request):
        """
        Gets ``username``, ``course_id``, and ``enterprise_customer_uuid``,
        which are the relevant query parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``username``, ``course_id``, and ``enterprise_customer_uuid`` from the request.

        """
        if request.method == 'GET':
            username = request.query_params.get(self.REQUIRED_PARAM_USERNAME, '')
            course_id = request.query_params.get(self.REQUIRED_PARAM_COURSE_ID, '')
            enterprise_customer_uuid = request.query_params.get(self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER)
        else:
            username = request.data.get(self.REQUIRED_PARAM_USERNAME, '')
            course_id = request.data.get(self.REQUIRED_PARAM_COURSE_ID, '')
            enterprise_customer_uuid = request.data.get(self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER)
        if not (username and course_id and enterprise_customer_uuid):
            raise ConsentAPIRequestError(
                self.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=username,
                    course_id=course_id,
                    enterprise_customer_uuid=enterprise_customer_uuid
                )
            )
        return username, course_id, enterprise_customer_uuid

    def set_consent_state(self, granted, user_id=None, course_id=None, enterprise_customer_uuid=None):
        """
        Sets the consent state (boolean) to ``granted`` for the relevant ``EnterpriseCourseEnrollment`` instance.

        :param granted: Whether to grant consent.
        :param user_id: The ID of the user associated with the enrollment.
        :param course_id: The ID of the course for which the user will grant/not grant consent.
        :param enterprise_customer_uuid: The UUID of the Enterprise that seeks consent.

        """
        enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
        enterprise_customer_user = get_enterprise_customer_user(enterprise_customer, user_id)
        enterprise_course_enrollment, __ = EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id
        )
        enterprise_course_enrollment.consent_granted = granted
        enterprise_course_enrollment.save()

    def get(self, request):
        """
        GET /consent/api/v1/data_sharing_consent?username=bob&course_id=id&enterprise_customer_uuid=uuid
        *username*
            The edX username from whom to get consent.
        *course_id*
            The course for which consent is granted.
        *enterprise_customer_uuid*
            The UUID of the enterprise customer that requires consent.

        """
        try:
            username, course_id, enterprise_customer_uuid = self.get_required_query_params(request)
        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        user_id = get_user_id(username)
        exists = consent_exists(user_id, course_id, enterprise_customer_uuid)
        provided = consent_provided(user_id, course_id, enterprise_customer_uuid)
        required = consent_required(user_id, course_id, enterprise_customer_uuid)
        return Response({
            self.REQUIRED_PARAM_USERNAME: username,
            self.REQUIRED_PARAM_COURSE_ID: course_id,
            self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: enterprise_customer_uuid,
            self.CONSENT_EXISTS: exists,
            self.CONSENT_GRANTED: provided,
            self.CONSENT_REQUIRED: required
        }, status=(HTTP_200_OK if exists else HTTP_404_NOT_FOUND))

    def post(self, request):
        """
        POST /consent/api/v1/data_sharing_consent

        Requires a JSON object of the following format:
        >>> {
        >>>     "username": "bob",
        >>>     "course_id": "course-v1:edX+DemoX+Demo_Course",
        >>>     "enterprise_customer_uuid": "enterprise-uuid-goes-right-here"
        >>> }

        Keys:
        *username*
            The edX username from whom to get consent.
        *course_id*
            The course for which consent is granted.
        *enterprise_customer_uuid*
            The UUID of the enterprise customer that requires consent.

        """
        try:
            username, course_id, enterprise_customer_uuid = self.get_required_query_params(request)
        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        user_id = get_user_id(username)
        self.set_consent_state(True, user_id, course_id, enterprise_customer_uuid)
        provided = consent_provided(user_id, course_id, enterprise_customer_uuid)
        required = consent_required(user_id, course_id, enterprise_customer_uuid)
        return Response({
            self.REQUIRED_PARAM_USERNAME: username,
            self.REQUIRED_PARAM_COURSE_ID: course_id,
            self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: enterprise_customer_uuid,
            self.CONSENT_EXISTS: True,
            self.CONSENT_GRANTED: provided,
            self.CONSENT_REQUIRED: required
        })

    def delete(self, request):
        """
        DELETE /consent/api/v1/data_sharing_consent

        Requires a JSON object of the following format:
        >>> {
        >>>     "username": "bob",
        >>>     "course_id": "course-v1:edX+DemoX+Demo_Course",
        >>>     "enterprise_customer_uuid": "enterprise-uuid-goes-right-here"
        >>> }

        Keys:
        *username*
            The edX username from whom to get consent.
        *course_id*
            The course for which consent is granted.
        *enterprise_customer_uuid*
            The UUID of the enterprise customer that requires consent.

        """
        try:
            username, course_id, enterprise_customer_uuid = self.get_required_query_params(request)
        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        user_id = get_user_id(username)
        self.set_consent_state(False, user_id, course_id, enterprise_customer_uuid)
        provided = consent_provided(user_id, course_id, enterprise_customer_uuid)
        required = consent_required(user_id, course_id, enterprise_customer_uuid)
        return Response({
            self.REQUIRED_PARAM_USERNAME: username,
            self.REQUIRED_PARAM_COURSE_ID: course_id,
            self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: enterprise_customer_uuid,
            self.CONSENT_EXISTS: True,
            self.CONSENT_GRANTED: provided,
            self.CONSENT_REQUIRED: required
        })
