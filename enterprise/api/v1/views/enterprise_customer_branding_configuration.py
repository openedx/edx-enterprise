"""
Views for the ``enterprise-customer-branding`` API endpoint.
"""

from edx_rbac.decorators import permission_required
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerBrandingConfigurationViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer-branding`` API endpoint.
    """
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = [MultiPartParser, FormParser]
    queryset = models.EnterpriseCustomerBrandingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerBrandingConfigurationSerializer

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer__slug',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
    lookup_field = 'enterprise_customer__slug'

    @action(methods=['patch'], detail=False, permission_classes=[permissions.IsAuthenticated])
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request, enterprise_uuid: enterprise_uuid)
    def update_branding(self, request, enterprise_uuid):
        """
        PATCH /enterprise/api/v1/enterprise-customer-branding/update_branding/uuid

        Requires enterprise customer uuid path parameter
        """
        try:
            enterprise_customer = models.EnterpriseCustomer.objects.get(uuid=enterprise_uuid)
            branding_configs = models.EnterpriseCustomerBrandingConfiguration.objects.filter(
                enterprise_customer=enterprise_customer)
            if len(branding_configs) > 0:
                branding_config = models.EnterpriseCustomerBrandingConfiguration.objects.get(
                    enterprise_customer=enterprise_customer)
            else:
                branding_config = models.EnterpriseCustomerBrandingConfiguration(
                    enterprise_customer=enterprise_customer)

            if 'logo' in request.data:
                branding_config.logo = request.data['logo']
            if 'primary_color' in request.data:
                branding_config.primary_color = request.data['primary_color']
            if 'secondary_color' in request.data:
                branding_config.secondary_color = request.data['secondary_color']
            if 'tertiary_color' in request.data:
                branding_config.tertiary_color = request.data['tertiary_color']
            branding_config.save()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                'Error with updating branding configuration'
            )
            return Response("Error with updating branding configuration", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response("Branding was updated", status=status.HTTP_204_NO_CONTENT)
