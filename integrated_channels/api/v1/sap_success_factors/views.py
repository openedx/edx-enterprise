"""
    Viewset for integrated_channels/v1/sap_success_factors/
"""
from edx_rbac.mixins import PermissionRequiredMixin
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication

from django.core.exceptions import PermissionDenied
from django.http import Http404

from enterprise.models import EnterpriseCustomerUser
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration

from .serializers import SAPSuccessFactorsConfigSerializer


class SAPSuccessFactorsConfigurationViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SAPSuccessFactorsConfigSerializer
    permission_required = 'enterprise.can_access_admin_dashboard'

    def get_queryset(self):
        enterprise_customer_users = EnterpriseCustomerUser.objects.filter(user_id=self.request.user.id)
        if enterprise_customer_users:
            enterprise_customers_uuids = [str(enterprise_customer_user.enterprise_customer.uuid) for
                                          enterprise_customer_user in enterprise_customer_users]
            enterprise_customer_uuid = self.request.query_params.get('enterprise_customer')

            if enterprise_customer_uuid:
                if enterprise_customer_uuid in enterprise_customers_uuids:
                    return SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.filter(
                        enterprise_customer__uuid=enterprise_customer_uuid
                    )
                raise PermissionDenied()
            return SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.filter(
                enterprise_customer__uuid__in=enterprise_customers_uuids
            )
        raise Http404
