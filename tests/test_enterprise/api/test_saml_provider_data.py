"""
Tests for enterprise.api.v1.views.saml_provider_data — SAMLProviderDataViewSet.
"""
import uuid
from unittest.mock import MagicMock, patch

from django.conf import settings
from rest_framework import status
from rest_framework.reverse import reverse

from enterprise.constants import ALL_ACCESS_CONTEXT, ENTERPRISE_ADMIN_ROLE
from test_utils import APITest
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory

PROVIDER_DATA_LIST_URL = reverse('enterprise-saml-provider-data-list')


class MockQuerySet:
    """
    A minimal queryset-like object that satisfies DRF's filter backends and pagination.
    """

    def __init__(self, items=None):
        self._items = list(items or [])

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __bool__(self):
        return bool(self._items)

    def __getitem__(self, key):
        return self._items[key]

    def filter(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self

    def count(self):
        return len(self._items)

    def get(self, **kwargs):
        if self._items:
            return self._items[0]
        raise Exception('No items')


def _mock_tpa_classes():
    """
    Build mock TPA classes: 5-tuple matching _get_tpa_classes return.
    """
    MockSAMLProviderConfig = MagicMock()
    MockSAMLProviderData = MagicMock()
    MockSerializer = MagicMock()
    mock_create_or_update = MagicMock()
    mock_parse = MagicMock()
    return MockSAMLProviderConfig, MockSAMLProviderData, MockSerializer, mock_create_or_update, mock_parse


class TestSAMLProviderDataViewSet(APITest):
    """Tests for SAMLProviderDataViewSet."""

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_uuid = str(self.enterprise_customer.uuid)
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

    # -- get_queryset tests --

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_get_queryset_filters_by_entity_id(self, mock_tpa):
        mocks = _mock_tpa_classes()
        MockSAMLProviderConfig, MockSAMLProviderData, MockSerializer = mocks[0], mocks[1], mocks[2]
        # Configure serializer mock so DRF's list response completes.
        mock_ser_instance = MagicMock()
        mock_ser_instance.data = []
        MockSerializer.return_value = mock_ser_instance
        mock_tpa.return_value = mocks

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        MockSAMLProviderConfig.objects.current_set.return_value.get.return_value = mock_saml_provider
        MockSAMLProviderData.objects.filter.return_value = MockQuerySet()

        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={self.enterprise_uuid}'
        self.client.get(settings.TEST_SERVER + url)

        MockSAMLProviderConfig.objects.current_set.return_value.get.assert_called_once_with(slug='testslug')
        MockSAMLProviderData.objects.filter.assert_called_once_with(entity_id='http://test-entity')

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_get_queryset_filters_by_pk_when_provided(self, mock_tpa):
        mocks = _mock_tpa_classes()
        MockSAMLProviderConfig, MockSAMLProviderData, MockSerializer = mocks[0], mocks[1], mocks[2]
        mock_ser_instance = MagicMock()
        mock_ser_instance.data = {'id': 5}
        MockSerializer.return_value = mock_ser_instance
        mock_tpa.return_value = mocks

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        MockSAMLProviderConfig.objects.current_set.return_value.get.return_value = mock_saml_provider

        mock_data_obj = MagicMock()
        mock_data_obj.id = 5
        mock_data_obj.pk = 5
        MockSAMLProviderData.objects.filter.return_value = MockQuerySet([mock_data_obj])

        detail_url = reverse('enterprise-saml-provider-data-detail', kwargs={'pk': 5})
        url = f'{detail_url}?enterprise-id={self.enterprise_uuid}'
        self.client.get(settings.TEST_SERVER + url)

        MockSAMLProviderData.objects.filter.assert_called_once_with(id='5')

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_get_queryset_raises_parse_error_when_no_uuid(self, mock_tpa):
        mock_tpa.return_value = _mock_tpa_classes()

        response = self.client.get(settings.TEST_SERVER + PROVIDER_DATA_LIST_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_get_queryset_returns_404_when_no_idp(self, mock_tpa):
        mock_tpa.return_value = _mock_tpa_classes()

        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={nonexistent_uuid}'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_get_queryset_returns_404_when_no_saml_provider(self, mock_tpa):
        mocks = _mock_tpa_classes()
        mock_tpa.return_value = mocks
        MockSAMLProviderConfig = mocks[0]

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        MockSAMLProviderConfig.DoesNotExist = type('DoesNotExist', (Exception,), {})
        MockSAMLProviderConfig.objects.current_set.return_value.get.side_effect = MockSAMLProviderConfig.DoesNotExist

        url = f'{PROVIDER_DATA_LIST_URL}?enterprise-id={self.enterprise_uuid}'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # -- sync_provider_data tests --

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_sync_provider_data_success(self, mock_tpa, mock_fetch):
        mocks = _mock_tpa_classes()
        mock_tpa.return_value = mocks
        MockSAMLProviderConfig = mocks[0]
        mock_create_or_update = mocks[3]
        mock_parse = mocks[4]

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        MockSAMLProviderConfig.objects.current_set.return_value.get.return_value = mock_saml_provider
        MockSAMLProviderConfig.DoesNotExist = type('DoesNotExist', (Exception,), {})

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

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_sync_provider_data_invalid_uuid(self, mock_tpa):
        mock_tpa.return_value = _mock_tpa_classes()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': 'bad-uuid'},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_sync_provider_data_no_matching_idp(self, mock_tpa):
        mock_tpa.return_value = _mock_tpa_classes()

        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': nonexistent_uuid},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_sync_provider_data_no_matching_saml_provider(self, mock_tpa, mock_fetch):
        mocks = _mock_tpa_classes()
        mock_tpa.return_value = mocks
        MockSAMLProviderConfig = mocks[0]

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        MockSAMLProviderConfig.DoesNotExist = type('DoesNotExist', (Exception,), {})
        MockSAMLProviderConfig.objects.current_set.return_value.get.side_effect = MockSAMLProviderConfig.DoesNotExist

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def _test_sync_fetch_error(self, exc_class, mock_tpa, mock_fetch):
        """Helper for testing various fetch errors."""
        mocks = _mock_tpa_classes()
        mock_tpa.return_value = mocks
        MockSAMLProviderConfig = mocks[0]

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        MockSAMLProviderConfig.objects.current_set.return_value.get.return_value = mock_saml_provider
        MockSAMLProviderConfig.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_fetch.side_effect = exc_class('error')

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_sync_provider_data_fetch_ssl_error(self):
        from requests.exceptions import SSLError
        self._test_sync_fetch_error(SSLError)

    def test_sync_provider_data_fetch_missing_schema(self):
        from requests.exceptions import MissingSchema
        self._test_sync_fetch_error(MissingSchema)

    def test_sync_provider_data_fetch_http_error(self):
        from requests.exceptions import HTTPError
        self._test_sync_fetch_error(HTTPError)

    @patch('enterprise.api.v1.views.saml_provider_data.fetch_metadata_xml')
    @patch('enterprise.api.v1.views.saml_provider_data.SAMLProviderDataViewSet._get_tpa_classes')
    def test_sync_provider_data_parse_returns_none(self, mock_tpa, mock_fetch):
        mocks = _mock_tpa_classes()
        mock_tpa.return_value = mocks
        MockSAMLProviderConfig = mocks[0]
        mock_parse = mocks[4]

        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        )

        mock_saml_provider = MagicMock()
        mock_saml_provider.entity_id = 'http://test-entity'
        mock_saml_provider.metadata_source = 'https://idp.example.com/metadata'
        MockSAMLProviderConfig.objects.current_set.return_value.get.return_value = mock_saml_provider
        MockSAMLProviderConfig.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_fetch.return_value = MagicMock()
        mock_parse.return_value = None

        sync_url = reverse('enterprise-saml-provider-data-sync-provider-data')
        response = self.client.post(
            settings.TEST_SERVER + sync_url,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Failed to parse' in response.data['error']
