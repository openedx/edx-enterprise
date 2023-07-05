"""
Views for the Admin Notification API.
"""


from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import APIView

from enterprise import models
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.errors import AdminNotificationAPIRequestError
from enterprise.logging import getEnterpriseLogger
from enterprise.utils import get_request_value

LOGGER = getEnterpriseLogger(__name__)


class NotificationReadView(APIView):
    """
    API to mark notifications as read.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_NOTIFICATION_ID = 'notification_id'
    REQUIRED_PARAM_ENTERPRISE_SLUG = 'enterprise_slug'

    MISSING_REQUIRED_PARAMS_MSG = 'Some required parameter(s) missing: {}'

    def get_required_query_params(self, request):
        """
        Gets ``notification_id`` and ``enterprise_slug``.
        which are the relevant parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``notification_id`` and ``enterprise_slug`` from the request.
        """
        enterprise_slug = get_request_value(request, self.REQUIRED_PARAM_ENTERPRISE_SLUG, '')
        notification_id = get_request_value(request, self.REQUIRED_PARAM_NOTIFICATION_ID, '')
        if not (notification_id and enterprise_slug):
            raise AdminNotificationAPIRequestError(
                self.get_missing_params_message([
                    (self.REQUIRED_PARAM_NOTIFICATION_ID, bool(notification_id)),
                    (self.REQUIRED_PARAM_ENTERPRISE_SLUG, bool(enterprise_slug)),
                ])
            )
        return notification_id, enterprise_slug

    def get_missing_params_message(self, parameter_state):
        """
        Get a user-friendly message indicating a missing parameter for the API endpoint.
        """
        params = ', '.join(name for name, present in parameter_state if not present)
        return self.MISSING_REQUIRED_PARAMS_MSG.format(params)

    @permission_required('enterprise.can_access_admin_dashboard')
    def post(self, request):
        """
        POST /enterprise/api/v1/read_notification

        Requires a JSON object of the following format::

            {
                'notification_id': 1,
                'enterprise_slug': 'enterprise_slug',
            }

        Keys:
            notification_id: Notification ID which is read by Current User.
            enterprise_slug: The slug of the enterprise.
        """
        try:
            notification_id, enterprise_slug = self.get_required_query_params(request)
        except AdminNotificationAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        try:
            data = {
                self.REQUIRED_PARAM_NOTIFICATION_ID: notification_id,
                self.REQUIRED_PARAM_ENTERPRISE_SLUG: enterprise_slug,
            }
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(
                enterprise_customer__slug=enterprise_slug, user_id=request.user.id
            )
            notification_read, _ = models.AdminNotificationRead.objects.get_or_create(
                enterprise_customer_user=enterprise_customer_user,
                admin_notification_id=notification_id,
                is_read=True
            )
            LOGGER.info(
                '[Admin Notification API] Notification read request successful. AdminNotificationRead ID'
                ' {}.'.format(notification_read.id)
            )
            return Response(data, status=HTTP_200_OK)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error(
                '[Admin Notification API] Notification read request failed, AdminNotification ID:{},Enterprise Slug:{}'
                ' User ID:{}, Exception:{}.'.format(notification_id, enterprise_slug, request.user.id, exc)
            )
            return Response(
                {'error': 'Notification read request failed'},
                status=HTTP_500_INTERNAL_SERVER_ERROR
            )
