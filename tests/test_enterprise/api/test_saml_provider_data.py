"""
Tests for enterprise.api.v1.views.saml_provider_data — SAMLProviderDataViewSet.
"""
import uuid
from unittest.mock import MagicMock, patch

from django_mock_queries.query import MockSet
from requests.exceptions import HTTPError, MissingSchema, SSLError
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

from enterprise.constants import ALL_ACCESS_CONTEXT, ENTERPRISE_ADMIN_ROLE
from test_utils import APITest
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory

PROVIDER_DATA_LIST_URL = reverse('enterprise-saml-provider-data-list')


class TestSAMLProviderDataViewSet(APITest):
    """Tests for SAMLProviderDataViewSet."""

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_uuid = str(self.enterprise_customer.uuid)
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

    # -- get_queryset tests --

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_filters_by_entity_id(
        self, mock_saml_provider_config, mock_saml_provider_data, mock_serializer_cls,
    ):
        # Configure serializer mock so DRF's list response completes.
        mock_ser_instance = MagicMock()
        mock_ser_instance.data = []
        mock_serializer_cls.return_value = mock_ser_instance

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider_config.objects.current_set.return_value.get.return_value = mock_saml_provider
        mock_saml_provider_data.objects.filter.return_value = MockSet()

        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={self.enterprise_uuid}'
        self.client.get(settings.TEST_SERVER + url)

        mock_saml_provider_config.objects.current_set.return_value.get.assert_called_once_with(slug='testslug')
        mock_saml_provider_data.objects.filter.assert_called_once_with(entity_id='http://test-entity')

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_filters_by_pk_when_provided(
        self, mock_saml_provider_config, mock_saml_provider_data, mock_serializer_cls,
    ):
        mock_ser_instance = MagicMock()
        mock_ser_instance.data = {'id': 5}
        mock_serializer_cls.return_value = mock_ser_instance

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider_config.objects.current_set.return_value.get.return_value = mock_saml_provider

        mock_data_obj = MagicMock()
        mock_data_obj.id = '5'
        mock_data_obj.pk = '5'
        mock_saml_provider_data.objects.filter.return_value = MockSet(mock_data_obj)

        detail_url = reverse('enterprise-saml-provider-data-detail', kwargs={'pk': 5})
        url = f'{detail_url}?enterprise-id={self.enterprise_uuid}'
        self.client.get(settings.TEST_SERVER + url)

        mock_saml_provider_data.objects.filter.assert_called_once_with(id='5')

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_raises_parse_error_when_no_uuid(
        self, _mock_saml_provider_config, _mock_saml_provider_data, _mock_serializer_cls,
    ):
        response = self.client.get(settings.TEST_SERVER + PROVIDER_DATA_LIST_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_returns_404_when_no_idp(
        self, _mock_saml_provider_config, _mock_saml_provider_data, _mock_serializer_cls,
    ):
        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={nonexistent_uuid}'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_returns_404_when_no_saml_provider(
        self, mock_saml_provider_config, _mock_saml_provider_data, _mock_serializer_cls,
    ):
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider_config.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_saml_provider_config.objects.current_set.return_value.get.side_effect = (
            mock_saml_provider_config.DoesNotExist
        )

        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={self.enterprise_uuid}'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataSerializer')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderData')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_get_queryset_raises_parse_error_when_uuid_invalid(
        self, _mock_saml_provider_config, _mock_saml_provider_data, _mock_serializer_cls,
    ):
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id=not-a-uuid'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -- sync_provider_data tests --

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.create_or_update_bulk_saml_provider_data')
    @patch('enterprise.api.v1.views.saml_provider_data.parse_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_sync_provider_data_success(self, mock_saml_provider_config, mock_parse, mock_create_or_update, mock_fetch):
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        mock_saml_provider_config.objects.current_set.return_value.get.return_value = mock_saml_provider
        mock_saml_provider_config.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_xml = MagicMock()
        mock_fetch.return_value = mock_xml
        mock_parse.return_value = (['pubkey1'], 'https://sso.example.com', None)

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_fetch.assert_called_once_with('https://idp.example.com/metadata')
        mock_parse.assert_called_once_with(mock_xml, 'http://test-entity')
        mock_create_or_update.assert_called_once_with(
            'http://test-entity', ['pubkey1'], 'https://sso.example.com', None,
        )

    def test_sync_provider_data_invalid_uuid(self):
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': 'bad-uuid'},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sync_provider_data_no_matching_idp(self):
        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': nonexistent_uuid},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_sync_provider_data_no_matching_saml_provider(self, mock_saml_provider_config, _mock_fetch):
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider_config.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_saml_provider_config.objects.current_set.return_value.get.side_effect = (
            mock_saml_provider_config.DoesNotExist
        )

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def _test_sync_fetch_error(self, exc_class, mock_saml_provider_config, mock_fetch):
        """Helper for testing various fetch errors."""
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        mock_saml_provider_config.objects.current_set.return_value.get.return_value = mock_saml_provider
        mock_saml_provider_config.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_fetch.side_effect = exc_class('error')

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_sync_provider_data_fetch_ssl_error(self):
        self._test_sync_fetch_error(SSLError)  # pylint: disable=no-value-for-parameter

    def test_sync_provider_data_fetch_missing_schema(self):
        self._test_sync_fetch_error(MissingSchema)  # pylint: disable=no-value-for-parameter

    def test_sync_provider_data_fetch_http_error(self):
        self._test_sync_fetch_error(HTTPError)  # pylint: disable=no-value-for-parameter

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.parse_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderConfig')
    def test_sync_provider_data_parse_returns_none(self, mock_saml_provider_config, mock_parse, mock_fetch):
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        mock_saml_provider_config.objects.current_set.return_value.get.return_value = mock_saml_provider
        mock_saml_provider_config.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_fetch.return_value = MagicMock()
        mock_parse.return_value = None

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Failed to parse' in response.data['error']
