"""
Views for coupon codes.
"""

from smtplib import SMTPException

from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import APIView

from django.apps import apps
from django.core import mail
from django.utils.translation import gettext as _

from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.utils import create_message_body
from enterprise.errors import CodesAPIRequestError
from enterprise.logging import getEnterpriseLogger
from enterprise.utils import get_request_value

LOGGER = getEnterpriseLogger(__name__)


class CouponCodesView(APIView):
    """
    API to request coupon codes.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_EMAIL = 'email'
    REQUIRED_PARAM_ENTERPRISE_NAME = 'enterprise_name'
    OPTIONAL_PARAM_NUMBER_OF_CODES = 'number_of_codes'
    OPTIONAL_PARAM_NOTES = 'notes'

    MISSING_REQUIRED_PARAMS_MSG = "Some required parameter(s) missing: {}"

    def get_required_query_params(self, request):
        """
        Gets ``email``, ``enterprise_name``, ``number_of_codes``, and ``notes``,
        which are the relevant parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``email``, ``enterprise_name``, ``number_of_codes`` and ``notes`` from the request.
        """
        email = get_request_value(request, self.REQUIRED_PARAM_EMAIL, '')
        enterprise_name = get_request_value(request, self.REQUIRED_PARAM_ENTERPRISE_NAME, '')
        number_of_codes = get_request_value(request, self.OPTIONAL_PARAM_NUMBER_OF_CODES, '')
        notes = get_request_value(request, self.OPTIONAL_PARAM_NOTES, '')
        if not (email and enterprise_name):
            raise CodesAPIRequestError(
                self.get_missing_params_message([
                    (self.REQUIRED_PARAM_EMAIL, bool(email)),
                    (self.REQUIRED_PARAM_ENTERPRISE_NAME, bool(enterprise_name)),
                ])
            )
        return email, enterprise_name, number_of_codes, notes

    def get_missing_params_message(self, parameter_state):
        """
        Get a user-friendly message indicating a missing parameter for the API endpoint.
        """
        params = ', '.join(name for name, present in parameter_state if not present)
        return self.MISSING_REQUIRED_PARAMS_MSG.format(params)

    @permission_required('enterprise.can_access_admin_dashboard')
    def post(self, request):
        """
        POST /enterprise/api/v1/request_codes

        Requires a JSON object of the following format::

            {
                "email": "bob@alice.com",
                "enterprise_name": "IBM",
                "number_of_codes": "50",
                "notes": "Help notes for codes request",
            }

        Keys:
            email: Email of the customer who has requested more codes.
            enterprise_name: The name of the enterprise requesting more codes.
            number_of_codes: The number of codes requested.
            notes: Help notes related to codes request.
        """
        try:
            email, enterprise_name, number_of_codes, notes = self.get_required_query_params(request)
        except CodesAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        subject_line = _('Code Management - Request for Codes by {token_enterprise_name}').format(
            token_enterprise_name=enterprise_name
        )
        body_msg = create_message_body(email, enterprise_name, number_of_codes, notes)
        app_config = apps.get_app_config("enterprise")
        from_email_address = app_config.enterprise_integrations_email
        cs_email = app_config.customer_success_email
        data = {
            self.REQUIRED_PARAM_EMAIL: email,
            self.REQUIRED_PARAM_ENTERPRISE_NAME: enterprise_name,
            self.OPTIONAL_PARAM_NUMBER_OF_CODES: number_of_codes,
            self.OPTIONAL_PARAM_NOTES: notes,
        }
        try:
            messages_sent = mail.send_mail(
                subject_line,
                body_msg,
                from_email_address,
                [cs_email],
                fail_silently=False
            )
            LOGGER.info('[Enterprise API] Coupon code request emails sent: %s', messages_sent)
            return Response(data, status=HTTP_200_OK)
        except SMTPException:
            error_message = _(
                '[Enterprise API] Failure in sending e-mail to support.'
                ' SupportEmail: {token_cs_email}, UserEmail: {token_email}, EnterpriseName: {token_enterprise_name}'
            ).format(
                token_cs_email=cs_email,
                token_email=email,
                token_enterprise_name=enterprise_name
            )
            LOGGER.error(error_message)
            return Response(
                {'error': 'Request codes email could not be sent'},
                status=HTTP_500_INTERNAL_SERVER_ERROR
            )
