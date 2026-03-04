"""
Viewset for enterprise SAML provider data administration.
"""
import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from edx_rbac.mixins import PermissionRequiredMixin
from requests.exceptions import HTTPError, MissingSchema, SSLError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from enterprise.models import EnterpriseCustomerIdentityProvider

log = logging.getLogger(__name__)


class SAMLProviderDataViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    """
    A View to handle SAMLProviderData CRUD for enterprise admin users.

    Usage::

        GET  /enterprise/api/v1/auth/saml/v0/provider_data/?enterprise-id=<uuid>
        POST /enterprise/api/v1/auth/saml/v0/provider_data/
        PATCH /enterprise/api/v1/auth/saml/v0/provider_data/<pk>/
        DELETE /enterprise/api/v1/auth/saml/v0/provider_data/<pk>/
        POST /enterprise/api/v1/auth/saml/v0/provider_data/sync_provider_data
    """

    permission_classes = [permissions.IsAuthenticated]
    permission_required = 'enterprise.can_access_admin_dashboard'

    def _get_tpa_classes(self):
        # Deferred import — TPA models live in openedx-platform.
        from common.djangoapps.third_party_auth.models import SAMLProviderConfig, SAMLProviderData  # pylint: disable=import-outside-toplevel
        from common.djangoapps.third_party_auth.samlproviderdata.serializers import SAMLProviderDataSerializer  # pylint: disable=import-outside-toplevel
        from common.djangoapps.third_party_auth.utils import (  # pylint: disable=import-outside-toplevel
            convert_saml_slug_provider_id,
            create_or_update_bulk_saml_provider_data,
            fetch_metadata_xml,
            parse_metadata_xml,
            validate_uuid4_string,
        )
        return (
            SAMLProviderConfig, SAMLProviderData, SAMLProviderDataSerializer,
            convert_saml_slug_provider_id, create_or_update_bulk_saml_provider_data,
            fetch_metadata_xml, parse_metadata_xml, validate_uuid4_string,
        )

    def get_serializer_class(self):
        _, _, SAMLProviderDataSerializer, *_ = self._get_tpa_classes()
        return SAMLProviderDataSerializer

    def get_queryset(self):
        SAMLProviderConfig, SAMLProviderData, _, convert_saml_slug_provider_id, *_ = self._get_tpa_classes()
        if self.requested_enterprise_uuid is None:
            raise ParseError('Required enterprise_customer_uuid is missing')
        enterprise_customer_idp = get_object_or_404(
            EnterpriseCustomerIdentityProvider,
            enterprise_customer__uuid=self.requested_enterprise_uuid
        )
        try:
            saml_provider = SAMLProviderConfig.objects.current_set().get(
                slug=convert_saml_slug_provider_id(enterprise_customer_idp.provider_id))
        except SAMLProviderConfig.DoesNotExist:
            raise Http404('No matching SAML provider found.')  # pylint: disable=raise-missing-from
        provider_data_id = self.request.parser_context.get('kwargs', {}).get('pk')
        if provider_data_id:
            return SAMLProviderData.objects.filter(id=provider_data_id)
        return SAMLProviderData.objects.filter(entity_id=saml_provider.entity_id)

    @property
    def requested_enterprise_uuid(self):
        return (
            self.request.query_params.get('enterprise-id') or
            self.request.data.get('enterprise_customer_uuid')
        )

    def get_permission_object(self):
        return self.requested_enterprise_uuid

    @action(detail=False, methods=['post'], url_path='sync_provider_data')
    def sync_provider_data(self, request):
        (SAMLProviderConfig, _, _, convert_saml_slug_provider_id, create_or_update_bulk_saml_provider_data,
         fetch_metadata_xml, parse_metadata_xml, validate_uuid4_string) = self._get_tpa_classes()
        enterprise_customer_uuid = request.data.get('enterprise_customer_uuid')
        if not validate_uuid4_string(enterprise_customer_uuid):
            raise ParseError('enterprise_customer_uuid is not a valid uuid4')
        enterprise_customer_idp = get_object_or_404(
            EnterpriseCustomerIdentityProvider,
            enterprise_customer__uuid=enterprise_customer_uuid
        )
        try:
            saml_provider = SAMLProviderConfig.objects.current_set().get(
                slug=convert_saml_slug_provider_id(enterprise_customer_idp.provider_id))
        except SAMLProviderConfig.DoesNotExist:
            raise Http404('No matching SAML provider found.')  # pylint: disable=raise-missing-from
        metadata_url = saml_provider.metadata_source
        try:
            xml = fetch_metadata_xml(metadata_url)
        except (SSLError, MissingSchema, HTTPError) as exc:
            return Response(
                data={'error': f'Failed to fetch metadata XML: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = parse_metadata_xml(xml, saml_provider.entity_id)
        if result is None:
            return Response(
                data={'error': 'Failed to parse metadata XML.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        public_key, sso_url, expires_at = result
        create_or_update_bulk_saml_provider_data(public_key, sso_url, expires_at, saml_provider.entity_id)
        return Response(
            data={'message': 'Synced provider data successfully.'},
            status=status.HTTP_200_OK,
        )
