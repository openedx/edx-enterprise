"""
Tests for enterprise.api.v1.views.saml_provider_config — SAMLProviderConfigViewSet.
"""
import uuid
from unittest.mock import MagicMock, patch

from django_mock_queries.query import MockSet
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings
from django.db.utils import IntegrityError

from enterprise.constants import ALL_ACCESS_CONTEXT, ENTERPRISE_ADMIN_ROLE
from enterprise.models import EnterpriseCustomerIdentityProvider
from test_utils import APITest
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory

PROVIDER_CONFIG_LIST_URL = reverse('enterprise-saml-provider-config-list')


class TestSAMLProviderConfigViewSet(APITest):
    """Tests for SAMLProviderConfigViewSet."""

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_uuid = str(self.enterprise_customer.uuid)
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, self.enterprise_uuid)

    # -- get_queryset tests --

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_get_queryset_filters_by_enterprise_idp(self, mock_saml_provider_config, mock_serializer_cls):
        # Configure the serializer mock to return valid data for DRF's list response.
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.data = [{'id': 1}]
        mock_serializer_cls.return_value = mock_serializer_instance

        idp = EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-test',
        )

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.provider_id = idp.provider_id
        mock_saml_provider_config.objects.current_set.return_value.filter.return_value = MockSet(mock_config)

        url = f'{PROVIDER_CONFIG_LIST_URL}?enterprise-id={self.enterprise_uuid}'
        self.client.get(settings.TEST_SERVER + url)

        mock_saml_provider_config.objects.current_set.return_value.filter.assert_called_once_with(
            slug__in=['test'],
        )

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_get_queryset_raises_parse_error_when_no_uuid(self, _mock_saml_provider_config, _mock_serializer_cls):
        response = self.client.get(settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_get_queryset_returns_404_when_no_idp(self, _mock_saml_provider_config, _mock_serializer_cls):
        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        url = f'{PROVIDER_CONFIG_LIST_URL}?enterprise-id={nonexistent_uuid}'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_get_queryset_raises_parse_error_when_uuid_invalid(self, _mock_saml_provider_config, _mock_serializer_cls):
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        url = f'{PROVIDER_CONFIG_LIST_URL}?enterprise-id=not-a-uuid'
        response = self.client.get(settings.TEST_SERVER + url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigViewSet.get_object')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_destroy_raises_parse_error_when_uuid_invalid(
        self, _mock_saml_provider_config, _mock_serializer_cls, mock_get_object,
    ):
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        mock_config = MagicMock()
        mock_config.id = 42
        mock_config.pk = 42
        mock_config.provider_id = 'saml-test'
        mock_get_object.return_value = mock_config

        detail_url = reverse('enterprise-saml-provider-config-detail', kwargs={'pk': 42})
        response = self.client.delete(
            settings.TEST_SERVER + f'{detail_url}?enterprise-id=not-a-uuid'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -- create tests --

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_create_saves_config_and_creates_idp_association(self, _mock_saml_provider_config, mock_serializer_cls):
        mock_instance = MagicMock()
        mock_instance.slug = 'testslug'
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.save.return_value = mock_instance
        mock_serializer_instance.data = {'id': 1, 'slug': 'testslug'}
        mock_serializer_cls.return_value = mock_serializer_instance

        response = self.client.post(
            settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_serializer_instance.save.assert_called_once()
        assert EnterpriseCustomerIdentityProvider.objects.filter(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-testslug',
        ).exists()

    def test_create_raises_parse_error_when_uuid_missing(self):
        response = self.client.post(
            settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL,
            data={},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_raises_parse_error_when_uuid_invalid(self):
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        response = self.client.post(
            settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL,
            data={'enterprise_customer_uuid': 'not-a-uuid'},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_raises_validation_error_when_customer_not_found(self):
        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)
        response = self.client.post(
            settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL,
            data={'enterprise_customer_uuid': nonexistent_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_create_raises_validation_error_on_integrity_error(self, _mock_saml_provider_config, mock_serializer_cls):
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.save.side_effect = IntegrityError('duplicate')
        mock_serializer_cls.return_value = mock_serializer_instance

        response = self.client.post(
            settings.TEST_SERVER + PROVIDER_CONFIG_LIST_URL,
            data={'enterprise_customer_uuid': self.enterprise_uuid},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -- destroy tests --

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigViewSet.get_object')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_destroy_archives_config_and_deletes_idp(
        self, mock_saml_provider_config, _mock_serializer_cls, mock_get_object,
    ):
        EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-test',
        )

        mock_config = MagicMock()
        mock_config.id = 42
        mock_config.pk = 42
        mock_config.provider_id = 'saml-test'
        mock_get_object.return_value = mock_config

        detail_url = reverse('enterprise-saml-provider-config-detail', kwargs={'pk': 42})
        response = self.client.delete(
            settings.TEST_SERVER + f'{detail_url}?enterprise-id={self.enterprise_uuid}'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'id': 42}
        mock_saml_provider_config.objects.filter.assert_called_once_with(id=42)
        mock_saml_provider_config.objects.filter().update.assert_called_once_with(archived=True, enabled=False)
        assert not EnterpriseCustomerIdentityProvider.objects.filter(
            enterprise_customer=self.enterprise_customer,
            provider_id='saml-test',
        ).exists()

    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigViewSet.get_object')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfigSerializer')
    @patch('enterprise.api.v1.views.saml_provider_config.SAMLProviderConfig')
    def test_destroy_raises_validation_error_when_customer_not_found(
        self, _mock_saml_provider_config, _mock_serializer_cls, mock_get_object,
    ):
        mock_config = MagicMock()
        mock_config.id = 42
        mock_config.pk = 42
        mock_config.provider_id = 'saml-test'
        mock_get_object.return_value = mock_config

        nonexistent_uuid = str(uuid.uuid4())
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, nonexistent_uuid)

        detail_url = reverse('enterprise-saml-provider-config-detail', kwargs={'pk': 42})
        response = self.client.delete(
            settings.TEST_SERVER + f'{detail_url}?enterprise-id={nonexistent_uuid}'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
