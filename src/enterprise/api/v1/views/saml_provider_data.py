"""
Viewset for enterprise SAML provider data administration.
"""
import logging

from edx_rbac.mixins import PermissionRequiredMixin
from requests.exceptions import HTTPError, MissingSchema, SSLError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from django.http import Http404
from django.shortcuts import get_object_or_404

from enterprise.api.v1.views.saml_utils import (
    SAMLMetadataURLError,
    convert_saml_slug_provider_id,
    fetch_metadata_xml,
    validate_uuid4_string,
)
from enterprise.models import EnterpriseCustomerIdentityProvider

try:
    from common.djangoapps.third_party_auth.models import SAMLProviderConfig, SAMLProviderData
except ImportError:
    SAMLProviderConfig = None
    SAMLProviderData = None

try:
    from common.djangoapps.third_party_auth.samlproviderdata.serializers import SAMLProviderDataSerializer
except ImportError:
    SAMLProviderDataSerializer = None

try:
    from common.djangoapps.third_party_auth.utils import create_or_update_bulk_saml_provider_data, parse_metadata_xml
except ImportError:
    create_or_update_bulk_saml_provider_data = None
    parse_metadata_xml = None

log = logging.getLogger(__name__)


class SAMLProviderDataViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    """
    A View to handle SAMLProviderData CRUD for enterprise admin users.

    Usage::

        GET  /auth/saml/v0/provider_data/?enterprise_customer_uuid=<uuid>
        POST /auth/saml/v0/provider_data/
        PATCH /auth/saml/v0/provider_data/<pk>/
        DELETE /auth/saml/v0/provider_data/<pk>/
        POST /auth/saml/v0/provider_data/sync_provider_data
    """

    permission_classes = [permissions.IsAuthenticated]
    permission_required = 'enterprise.can_access_admin_dashboard'

    def get_serializer_class(self):
        return SAMLProviderDataSerializer

    def get_queryset(self):
        """
        Find and return the matching providerid for the given enterprise uuid.

        Note: There is no direct association between samlproviderdata and enterprisecustomer.
        So we make that association in code via samlproviderdata > samlproviderconfig (via entity_id)
        then, we fetch enterprisecustomer via samlproviderconfig > enterprisecustomer (via association table).
        """
        if self.requested_enterprise_uuid is None:
            raise ParseError('Required enterprise_customer_uuid query parameter or field is missing')
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
            return SAMLProviderData.objects.filter(
                id=provider_data_id,
                entity_id=saml_provider.entity_id,
            )
        return SAMLProviderData.objects.filter(entity_id=saml_provider.entity_id)

    @property
    def requested_enterprise_uuid(self):
        """The enterprise customer uuid from request params or post body."""
        value = (
            self.request.query_params.get('enterprise_customer_uuid') or
            self.request.data.get('enterprise_customer_uuid')
        )
        if value is not None and not validate_uuid4_string(value):
            raise ParseError('Invalid enterprise_customer_uuid')
        return value

    def get_permission_object(self):
        """Retrieve an EnterpriseCustomer to do auth against."""
        return self.requested_enterprise_uuid

    @action(detail=False, methods=['post'], url_path='sync_provider_data')
    def sync_provider_data(self, request):
        """Fetch and sync SAML provider metadata from the configured metadata URL."""
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
        except (SSLError, MissingSchema, HTTPError, SAMLMetadataURLError) as exc:
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
        public_keys, sso_url, expires_at = result
        create_or_update_bulk_saml_provider_data(saml_provider.entity_id, public_keys, sso_url, expires_at)
        return Response(
            data={'message': 'Synced provider data successfully.'},
            status=status.HTTP_200_OK,
        )
