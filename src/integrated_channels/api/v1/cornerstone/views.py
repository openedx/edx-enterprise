"""
Viewsets for integrated_channels/v1/cornerstone/
"""
from logging import getLogger

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from rest_framework.views import APIView

from django.contrib import auth
from django.db import transaction

from enterprise.api.throttles import ServiceUserThrottle
from enterprise.utils import get_enterprise_customer_or_404, get_enterprise_customer_user, localized_utcnow
from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.cornerstone.utils import create_cornerstone_learner_data

from .serializers import CornerstoneConfigSerializer

LOGGER = getLogger(__name__)
User = auth.get_user_model()


class CornerstoneConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    """Viewset for CornerstoneEnterpriseCustomerConfiguration"""
    serializer_class = CornerstoneConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = CornerstoneEnterpriseCustomerConfiguration


class CornerstoneLearnerInformationView(APIView):
    """Viewset for saving information of a cornerstone learner"""
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    def post(self, request):
        """
            An endpoint to save a cornerstone learner information received from frontend.
            integrated_channels/api/v1/cornerstone/save-learner-information
            Requires a JSON object in the following format:
                {
                    "courseKey": "edX+DemoX",
                    "enterpriseUUID": "enterprise-uuid-goes-right-here",
                    "userGuid": "user-guid-from-csod",
                    "callbackUrl": "https://example.com/csod/callback/1",
                    "sessionToken": "123123123",
                    "subdomain": "edx.csod.com"
                }
        """
        user_id = request.user.id
        enterprise_customer_uuid = request.data.get('enterpriseUUID')
        enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)
        course_key = request.data.get('courseKey')
        with transaction.atomic():
            csod_user_guid = request.data.get('userGuid')
            csod_callback_url = request.data.get('callbackUrl')
            csod_session_token = request.data.get('sessionToken')
            csod_subdomain = request.data.get("subdomain")

            if csod_session_token and csod_subdomain:
                LOGGER.info(
                    f'integrated_channel=CSOD, '
                    f'integrated_channel_enterprise_customer_uuid={enterprise_customer_uuid}, '
                    f'integrated_channel_lms_user={user_id}, '
                    f'integrated_channel_course_key={course_key}, '
                    'saving CSOD learner information'
                )
                cornerstone_customer_configuration = \
                    CornerstoneEnterpriseCustomerConfiguration.get_by_customer_and_subdomain(
                        enterprise_customer=enterprise_customer,
                        customer_subdomain=csod_subdomain
                    )
                if cornerstone_customer_configuration:
                    # check if request user is linked as a learner with the given enterprise before savin anything
                    enterprise_customer_user = get_enterprise_customer_user(user_id, enterprise_customer_uuid)
                    if enterprise_customer_user:
                        # saving session token in enterprise config to access cornerstone apis
                        cornerstone_customer_configuration.session_token = csod_session_token
                        cornerstone_customer_configuration.session_token_modified = localized_utcnow()
                        cornerstone_customer_configuration.save()
                        # saving learner information received from cornerstone
                        create_cornerstone_learner_data(
                            user_id,
                            csod_user_guid,
                            csod_session_token,
                            csod_callback_url,
                            csod_subdomain,
                            cornerstone_customer_configuration,
                            course_key
                        )
                    else:
                        LOGGER.error(
                            f'integrated_channel=CSOD, '
                            f'integrated_channel_enterprise_customer_uuid={enterprise_customer_uuid}, '
                            f'integrated_channel_lms_user={user_id}, '
                            f'integrated_channel_course_key={course_key}, '
                            f'user is not linked to the given enterprise'
                        )
                        message = (f'Cornerstone information could not be saved for learner with user_id={user_id}'
                                   f'because user is not linked to the given enterprise {enterprise_customer_uuid}')
                        return Response(data={'error': message}, status=HTTP_404_NOT_FOUND)
                else:
                    LOGGER.error(
                        f'integrated_channel=CSOD, '
                        f'integrated_channel_enterprise_customer_uuid={enterprise_customer_uuid}, '
                        f'integrated_channel_lms_user={user_id}, '
                        f'integrated_channel_course_key={course_key}, '
                        f'unable to find cornerstone config matching subdomain {csod_subdomain}'
                    )
                    message = (f'Cornerstone information could not be saved for learner with user_id={user_id}'
                               f'because no config exist with the subdomain {csod_subdomain}')
                    return Response(data={'error': message}, status=HTTP_404_NOT_FOUND)
            return Response(status=HTTP_200_OK)
