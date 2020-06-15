# -*- coding: utf-8 -*-
"""
A generic API for edX Enterprise's Consent application.
"""

from logging import getLogger

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from consent.api import permissions
from consent.errors import ConsentAPIRequestError
from consent.helpers import get_data_sharing_consent
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.utils import get_request_value

LOGGER = getLogger(__name__)


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
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_USERNAME = 'username'
    REQUIRED_PARAM_COURSE_ID = 'course_id'
    REQUIRED_PARAM_PROGRAM_UUID = 'program_uuid'
    REQUIRED_PARAM_ENTERPRISE_CUSTOMER = 'enterprise_customer_uuid'  # pylint: disable=invalid-name

    CONSENT_EXISTS = 'exists'
    CONSENT_GRANTED = 'consent_provided'
    CONSENT_REQUIRED = 'consent_required'

    MISSING_REQUIRED_PARAMS_MSG = "Some required parameter(s) missing: {}"

    def get_consent_record(self, request):
        """
        Get the consent record relevant to the request at hand.
        """
        username, course_id, program_uuid, enterprise_customer_uuid = self.get_required_query_params(request)
        dsc = get_data_sharing_consent(
            username,
            enterprise_customer_uuid,
            course_id=course_id,
            program_uuid=program_uuid
        )
        if not dsc:
            log_message = (
                '[Enterprise Consent API] The code was unable to get consent data for the user. '
                'Course: {course_id}, '
                'Program: {program_uuid}, '
                'EnterpriseCustomer: {enterprise_customer_uuid}, '
                'User: {username}, '
                'ErrorCode: {error_code}'.format(
                    course_id=course_id,
                    program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid,
                    username=username,
                    error_code='ENTGDS001',
                )
            )
            LOGGER.error(log_message)
        return dsc

    def get_required_query_params(self, request):
        """
        Gets ``username``, ``course_id``, and ``enterprise_customer_uuid``,
        which are the relevant query parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``username``, ``course_id``, and ``enterprise_customer_uuid`` from the request.
        """
        username = get_request_value(request, self.REQUIRED_PARAM_USERNAME, '')
        course_id = get_request_value(request, self.REQUIRED_PARAM_COURSE_ID, '')
        program_uuid = get_request_value(request, self.REQUIRED_PARAM_PROGRAM_UUID, '')
        enterprise_customer_uuid = get_request_value(request, self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER)
        if not (username and (course_id or program_uuid) and enterprise_customer_uuid):
            exception_message = self.get_missing_params_message([
                ("'username'", bool(username)),
                ("'enterprise_customer_uuid'", bool(enterprise_customer_uuid)),
                ("one of 'course_id' or 'program_uuid'", bool(course_id or program_uuid)),
            ])
            log_message = (
                '[Enterprise Consent API] Required request values missing for action to be carried out. '
                'Course: {course_id}, '
                'Program: {program_uuid}, '
                'EnterpriseCustomer: {enterprise_customer_uuid}, '
                'User: {username}, '
                'ErrorCode: {error_code}, '
                'Message: {message}'.format(
                    course_id=course_id,
                    program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid,
                    username=username,
                    error_code='ENTGDS000',
                    message=exception_message,
                )
            )
            LOGGER.error(log_message)
            raise ConsentAPIRequestError(exception_message)
        return username, course_id, program_uuid, enterprise_customer_uuid

    def get_missing_params_message(self, parameter_state):
        """
        Get a user-friendly message indicating a missing parameter for the API endpoint.
        """
        params = ', '.join(name for name, present in parameter_state if not present)
        return self.MISSING_REQUIRED_PARAMS_MSG.format(params)

    def get_no_record_response(self, request):
        """
        Get an HTTPResponse that can be used when there's no related EnterpriseCustomer.
        """
        username, course_id, program_uuid, enterprise_customer_uuid = self.get_required_query_params(request)
        data = {
            self.REQUIRED_PARAM_USERNAME: username,
            self.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: enterprise_customer_uuid,
            self.CONSENT_EXISTS: False,
            self.CONSENT_GRANTED: False,
            self.CONSENT_REQUIRED: False,
        }
        if course_id:
            data[self.REQUIRED_PARAM_COURSE_ID] = course_id

        if program_uuid:
            data[self.REQUIRED_PARAM_PROGRAM_UUID] = program_uuid

        return Response(data, status=HTTP_200_OK)

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
            consent_record = self.get_consent_record(request)
            if consent_record is None:
                return self.get_no_record_response(request)
        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        return Response(consent_record.serialize(), status=HTTP_200_OK)

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
            consent_record = self.get_consent_record(request)
            if consent_record is None:
                return self.get_no_record_response(request)
            if consent_record.consent_required():
                # If and only if the given EnterpriseCustomer requires data sharing consent
                # for the given course, then, since we've received a POST request, set the
                # consent state for the EC/user/course combo.
                consent_record.granted = True

                # Models don't have return values when saving, but ProxyDataSharingConsent
                # objects do - they should return either a model instance, or another instance
                # of ProxyDataSharingConsent if representing a multi-course consent record.
                consent_record = consent_record.save() or consent_record

        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        return Response(consent_record.serialize())

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
            consent_record = self.get_consent_record(request)
            if consent_record is None:
                return self.get_no_record_response(request)

            # We're fine with proactively refusing consent, even when there's no actual
            # requirement for consent yet.
            consent_record.granted = False

            # Models don't have return values when saving, but ProxyDataSharingConsent
            # objects do - they should return either a model instance, or another instance
            # of ProxyDataSharingConsent if representing a multi-course consent record.
            consent_record = consent_record.save() or consent_record

        except ConsentAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        return Response(consent_record.serialize())
