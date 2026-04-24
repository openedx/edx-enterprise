"""
Tests for enterprise.api.v1.views.saml_utils — utility functions migrated from
openedx-platform's third_party_auth/utils.py.
"""
from unittest.mock import MagicMock, patch

import ddt
import pytest
from lxml import etree
from requests.exceptions import HTTPError, SSLError

from django.test import TestCase, override_settings

from enterprise.api.v1.views.saml_utils import (
    SAMLMetadataURLError,
    convert_saml_slug_provider_id,
    fetch_metadata_xml,
    validate_saml_metadata_url,
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
        assert validate_uuid4_string(None) is False


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
        mock_get.assert_called_once_with('https://idp.example.com/metadata', verify=True, timeout=30)

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

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_invalid_url_raises_before_fetch(self, mock_get):
        with pytest.raises(SAMLMetadataURLError):
            fetch_metadata_xml('http://idp.example.com/metadata')
        mock_get.assert_not_called()


@ddt.ddt
class TestValidateSAMLMetadataURL(TestCase):
    """
    Tests for validate_saml_metadata_url.

    Uses pytest.raises rather than unittest-style assertRaises throughout for
    consistency and to take advantage of pytest's match= parameter.
    """

    @ddt.data(
        'https://idp.example.com/metadata',
        'https://1.1.1.1/metadata',
    )
    def test_valid_urls_pass(self, url):
        validate_saml_metadata_url(url)  # should not raise

    @ddt.data(
        ('http://idp.example.com/metadata', 'must use HTTPS'),
        ('ftp://idp.example.com/metadata', 'must use HTTPS'),
        ('https://', 'no hostname'),
    )
    @ddt.unpack
    def test_invalid_scheme_or_missing_hostname(self, url, expected_fragment):
        with pytest.raises(SAMLMetadataURLError, match=expected_fragment):
            validate_saml_metadata_url(url)

    @ddt.data(
        'https://127.0.0.1/metadata',       # IPv4 loopback
        'https://[::1]/metadata',            # IPv6 loopback
        'https://169.254.169.254/latest',    # AWS metadata endpoint
        'https://169.254.0.1/metadata',      # other link-local
        'https://[fe80::1]/metadata',        # IPv6 link-local
        'https://240.0.0.1/metadata',        # reserved (Class E)
    )
    def test_always_blocked_regardless_of_setting(self, url):
        for allow_private in (False, True):
            with override_settings(SAML_METADATA_URL_ALLOW_PRIVATE_IPS=allow_private):
                with pytest.raises(SAMLMetadataURLError):
                    validate_saml_metadata_url(url)

    @ddt.data(
        'https://10.0.0.1/metadata',
        'https://172.16.0.1/metadata',
        'https://192.168.1.1/metadata',
        'https://[fc00::1]/metadata',        # IPv6 unique local
    )
    def test_private_ip_blocked_by_default(self, url):
        with pytest.raises(SAMLMetadataURLError):
            validate_saml_metadata_url(url)

    @ddt.data(
        'https://10.0.0.1/metadata',
        'https://172.16.0.1/metadata',
        'https://192.168.1.1/metadata',
        'https://[fc00::1]/metadata',        # IPv6 unique local
    )
    @override_settings(SAML_METADATA_URL_ALLOW_PRIVATE_IPS=True)
    def test_private_ip_allowed_with_setting(self, url):
        validate_saml_metadata_url(url)  # should not raise
