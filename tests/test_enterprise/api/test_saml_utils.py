"""
Tests for enterprise.api.v1.views.saml_utils — utility functions migrated from
openedx-platform's third_party_auth/utils.py.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase
from lxml import etree
from requests.exceptions import HTTPError, SSLError

from enterprise.api.v1.views.saml_utils import (
    convert_saml_slug_provider_id,
    fetch_metadata_xml,
    validate_uuid4_string,
)


class TestValidateUUID4String(TestCase):
    """Tests for validate_uuid4_string."""

    def test_valid_uuid4(self):
        assert validate_uuid4_string('12345678-1234-4234-a234-123456789abc') is True

    def test_invalid_uuid_garbage(self):
        assert validate_uuid4_string('not-a-uuid') is False

    def test_invalid_uuid_empty(self):
        assert validate_uuid4_string('') is False

    def test_invalid_uuid_none(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_uuid4_string(None)


class TestConvertSAMLSlugProviderId(TestCase):
    """Tests for convert_saml_slug_provider_id."""

    def test_slug_to_provider_id(self):
        assert convert_saml_slug_provider_id('samltest') == 'saml-samltest'

    def test_provider_id_to_slug(self):
        assert convert_saml_slug_provider_id('saml-samltest') == 'samltest'

    def test_roundtrip(self):
        provider_names = {'saml-samltest': 'samltest', 'saml-example': 'example'}
        for provider_id, slug in provider_names.items():
            assert convert_saml_slug_provider_id(provider_id) == slug
            assert convert_saml_slug_provider_id(slug) == provider_id


class TestFetchMetadataXML(TestCase):
    """Tests for fetch_metadata_xml."""

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_success(self, mock_get):
        xml_content = b'<root><child/></root>'
        mock_response = MagicMock()
        mock_response.content = xml_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_metadata_xml('https://idp.example.com/metadata')
        assert result.tag == 'root'
        mock_get.assert_called_once_with('https://idp.example.com/metadata', verify=True)

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_ssl_error(self, mock_get):
        mock_get.side_effect = SSLError('SSL certificate verify failed')
        with self.assertRaises(SSLError):
            fetch_metadata_xml('https://idp.example.com/metadata')

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError('500 Server Error')
        mock_get.return_value = mock_response
        with self.assertRaises(HTTPError):
            fetch_metadata_xml('https://idp.example.com/metadata')

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_xml_syntax_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b'not xml at all'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        with self.assertRaises(etree.XMLSyntaxError):
            fetch_metadata_xml('https://idp.example.com/metadata')
