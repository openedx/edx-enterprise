"""
Viewset for enterprise SAML provider config administration.
"""
from django.db.utils import IntegrityError
from django.shortcuts import get_list_or_404
from edx_rbac.mixins import PermissionRequiredMixin
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.response import Response

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerIdentityProvider


class SAMLProviderConfigViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    """
    A View to handle SAMLProviderConfig CRUD for enterprise admin users.

    Usage::

        GET  /enterprise/api/v1/auth/saml/v0/provider_config/?enterprise-id=<uuid>
        POST /enterprise/api/v1/auth/saml/v0/provider_config/
        PATCH /enterprise/api/v1/auth/saml/v0/provider_config/<pk>/
        DELETE /enterprise/api/v1/auth/saml/v0/provider_config/<pk>/
    """

    permission_classes = [permissions.IsAuthenticated]
    permission_required = 'enterprise.can_access_admin_dashboard'

    def _get_tpa_classes(self):
        # Deferred import — TPA models live in openedx-platform.
        from common.djangoapps.third_party_auth.models import SAMLProviderConfig  # pylint: disable=import-outside-toplevel
        from common.djangoapps.third_party_auth.samlproviderconfig.serializers import SAMLProviderConfigSerializer  # pylint: disable=import-outside-toplevel
        from common.djangoapps.third_party_auth.utils import convert_saml_slug_provider_id, validate_uuid4_string  # pylint: disable=import-outside-toplevel
        return SAMLProviderConfig, SAMLProviderConfigSerializer, convert_saml_slug_provider_id, validate_uuid4_string

    def get_serializer_class(self):
        _, SAMLProviderConfigSerializer, _, _ = self._get_tpa_classes()
        return SAMLProviderConfigSerializer

    def get_queryset(self):
        SAMLProviderConfig, _, _, _ = self._get_tpa_classes()
        if self.requested_enterprise_uuid is None:
            raise ParseError('Required enterprise_customer_uuid is missing')
        enterprise_customer_idps = get_list_or_404(
            EnterpriseCustomerIdentityProvider,
            enterprise_customer__uuid=self.requested_enterprise_uuid
        )
        slug_list = [idp.provider_id for idp in enterprise_customer_idps]
        saml_config_ids = [
            config.id for config in SAMLProviderConfig.objects.current_set()
            if config.provider_id in slug_list
        ]
        return SAMLProviderConfig.objects.filter(id__in=saml_config_ids)

    def destroy(self, request, *args, **kwargs):
        SAMLProviderConfig, _, _, _ = self._get_tpa_classes()
        saml_provider_config = self.get_object()
        config_id = saml_provider_config.id
        provider_config_provider_id = saml_provider_config.provider_id
        customer_uuid = self.requested_enterprise_uuid
        try:
            enterprise_customer = EnterpriseCustomer.objects.get(pk=customer_uuid)
        except EnterpriseCustomer.DoesNotExist:
            raise ValidationError(f'Enterprise customer not found at uuid: {customer_uuid}')  # pylint: disable=raise-missing-from
        EnterpriseCustomerIdentityProvider.objects.filter(
            enterprise_customer=enterprise_customer,
            provider_id=provider_config_provider_id,
        ).delete()
        SAMLProviderConfig.objects.filter(id=config_id).update(archived=True, enabled=False)
        return Response(status=status.HTTP_200_OK, data={'id': config_id})

    def create(self, request, *args, **kwargs):
        SAMLProviderConfig, _, convert_saml_slug_provider_id, validate_uuid4_string = self._get_tpa_classes()
        enterprise_customer_uuid = request.data.get('enterprise_customer_uuid')
        if not enterprise_customer_uuid or not validate_uuid4_string(enterprise_customer_uuid):
            raise ParseError('enterprise_customer_uuid is missing or invalid')
        try:
            enterprise_customer = EnterpriseCustomer.objects.get(pk=enterprise_customer_uuid)
        except EnterpriseCustomer.DoesNotExist:
            raise ValidationError(f'Enterprise customer not found at uuid: {enterprise_customer_uuid}')  # pylint: disable=raise-missing-from
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            instance = serializer.save()
        except IntegrityError:
            raise ValidationError('SAML provider config with this entity_id already exists.')  # pylint: disable=raise-missing-from
        EnterpriseCustomerIdentityProvider.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            provider_id=convert_saml_slug_provider_id(instance.slug),
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @property
    def requested_enterprise_uuid(self):
        return (
            self.request.query_params.get('enterprise-id') or
            self.request.data.get('enterprise_customer_uuid')
        )

    def get_permission_object(self):
        return self.requested_enterprise_uuid
