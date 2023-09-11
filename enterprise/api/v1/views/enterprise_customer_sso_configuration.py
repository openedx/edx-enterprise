"""
Views for the ``enterprise-customer-sso-configuration`` API endpoint.
"""

from edx_rbac.decorators import permission_required
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from django.contrib import auth

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.logging import getEnterpriseLogger
from enterprise.tasks import send_sso_configured_email
from enterprise.utils import localized_utcnow

User = auth.get_user_model()

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerSsoConfigurationViewSet(viewsets.ModelViewSet):
    """
    API views for the ``EnterpriseCustomerSsoConfiguration`` model.
    """
    permission_classes = (permissions.IsAuthenticated,)
    queryset = models.EnterpriseCustomerSsoConfiguration.all_objects.all()

    serializer_class = serializers.EnterpriseCustomerSsoConfiguration

    # ``can_manage_enterprise_orchestration_configs`` maps to the edx operator system wide role. Meaning only operators
    # can complete orchestration record configuration process.
    @permission_required(
        'enterprise.can_manage_enterprise_orchestration_configs',
    )
    @action(methods=['post'], detail=True)
    def oauth_orchestration_complete(self, request, configuration_uuid, *args, **kwargs):
        """
        SSO orchestration completion callback. This endpoint is called by the SSO orchestrator when it has completed
        the configuration process.
        """
        # Make sure the config record exists
        sso_configuration_record = self.queryset.filter(pk=configuration_uuid).first()
        if not sso_configuration_record:
            return Response(status=HTTP_404_NOT_FOUND)

        if not sso_configuration_record.submitted_at:
            LOGGER.warning(
                f'SSO configuration record {sso_configuration_record.pk} has received a completion callback but has'
                ' not been marked as submitted.'
            )

        # Send a notification email to the enterprise associated with the configuration record
        send_sso_configured_email(sso_configuration_record.enterprise_customer.uuid)

        # Completing the orchestration process means the configuration record is now configured and can be considered
        # active
        sso_configuration_record.configured_at = localized_utcnow()
        sso_configuration_record.active = True
        sso_configuration_record.save()
        return Response(status=HTTP_200_OK)
