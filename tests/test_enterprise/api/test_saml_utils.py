"""
Tests for enterprise.api.v1.views.saml_utils — utility functions migrated from
openedx-platform's third_party_auth/utils.py.
"""
import io
import socket
from unittest.mock import MagicMock, patch

import ddt
import pytest
from lxml import etree
from requests.exceptions import HTTPError, SSLError
from requests.models import Response

from django.test import TestCase, override_settings

from enterprise.api.v1.views.saml_utils import (
    SAML_METADATA_MAX_REDIRECTS,
    SAMLMetadataURLError,
    convert_saml_slug_provider_id,
    fetch_metadata_xml,
    fetch_saml_metadata_response,
    validate_saml_metadata_url,
    validate_uuid4_string,
)


def mock_saml_metadata_dns(*addresses):
    """
    Patch the DNS lookup done when validating SAML metadata URLs.

    Tests use made-up IdP hostnames, so make them resolve to the given addresses
    (a public one by default) instead of going to the network.
    """
    addresses = addresses or ('93.184.215.14',)
    return patch(
        'enterprise.api.v1.views.saml_utils.getaddrinfo',
        return_value=[
            (socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
             (address, 443))
            for address in addresses
        ],
    )


def _metadata_response(status_code=200, location=None):
    """Build a requests Response, optionally redirecting to `location`."""
    response = Response()
    response.status_code = status_code
    response._content = b'<root><child/></root>'  # pylint: disable=protected-access
    response.raw = io.BytesIO()
    if location is not None:
        response.headers['Location'] = location
    return response


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

    def setUp(self):
        super().setUp()
        dns_patch = mock_saml_metadata_dns()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_success(self, mock_get):
        xml_content = b'<root><child/></root>'
        mock_response = MagicMock(is_redirect=False)
        mock_response.content = xml_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_metadata_xml('https://idp.example.com/metadata')
        assert result.tag == 'root'
        mock_get.assert_called_once_with(
            'https://idp.example.com/metadata', verify=True, timeout=30, allow_redirects=False,
        )

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_ssl_error(self, mock_get):
        mock_get.side_effect = SSLError('SSL certificate verify failed')
        with self.assertRaises(SSLError):
            fetch_metadata_xml('https://idp.example.com/metadata')

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_http_error(self, mock_get):
        mock_response = MagicMock(is_redirect=False)
        mock_response.raise_for_status.side_effect = HTTPError('500 Server Error')
        mock_get.return_value = mock_response
        with self.assertRaises(HTTPError):
            fetch_metadata_xml('https://idp.example.com/metadata')

    @patch('enterprise.api.v1.views.saml_utils.requests.get')
    def test_xml_syntax_error(self, mock_get):
        mock_response = MagicMock(is_redirect=False)
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
        with mock_saml_metadata_dns():
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

    @ddt.data(
        'https://0.0.0.0/metadata',                    # unspecified
        'https://224.0.0.1/metadata',                  # multicast
        'https://100.100.100.200/metadata',            # shared address space (Alibaba Cloud metadata)
        'https://[fd00:ec2::254]/metadata',            # AWS metadata endpoint over IPv6
        'https://[::ffff:169.254.169.254]/metadata',   # IPv4-mapped AWS metadata endpoint
    )
    def test_more_ip_literals_always_blocked(self, url):
        for allow_private in (False, True):
            with override_settings(SAML_METADATA_URL_ALLOW_PRIVATE_IPS=allow_private):
                with pytest.raises(SAMLMetadataURLError):
                    validate_saml_metadata_url(url)

    @ddt.data(
        '169.254.169.254',
        '127.0.0.1',
        '::1',
        'fd00:ec2::254',
        '0.0.0.0',
        '100.100.100.200',
        '::ffff:169.254.169.254',
        'fe80::1%eth0',
    )
    def test_hostname_resolving_to_forbidden_address_blocked(self, address):
        for allow_private in (False, True):
            with override_settings(SAML_METADATA_URL_ALLOW_PRIVATE_IPS=allow_private):
                with mock_saml_metadata_dns(address):
                    with pytest.raises(SAMLMetadataURLError, match='forbidden|publicly routable'):
                        validate_saml_metadata_url('https://idp.example.com/metadata')

    @ddt.data('10.0.0.5', '192.168.1.1', 'fc00::1')
    def test_hostname_resolving_to_private_address(self, address):
        with mock_saml_metadata_dns(address):
            with pytest.raises(SAMLMetadataURLError, match='private IP address'):
                validate_saml_metadata_url('https://idp.example.com/metadata')
            with override_settings(SAML_METADATA_URL_ALLOW_PRIVATE_IPS=True):
                validate_saml_metadata_url('https://idp.example.com/metadata')  # should not raise

    def test_every_resolved_address_is_checked(self):
        with mock_saml_metadata_dns('93.184.215.14', '169.254.169.254'):
            with pytest.raises(SAMLMetadataURLError, match='forbidden'):
                validate_saml_metadata_url('https://idp.example.com/metadata')

    def test_unresolvable_hostname_blocked(self):
        with patch(
            'enterprise.api.v1.views.saml_utils.getaddrinfo',
            side_effect=socket.gaierror('Name or service not known'),
        ):
            with pytest.raises(SAMLMetadataURLError, match='could not be resolved'):
                validate_saml_metadata_url('https://idp.example.com/metadata')

    def test_hostname_resolving_to_invalid_address_blocked(self):
        with mock_saml_metadata_dns('not-an-ip'):
            with pytest.raises(SAMLMetadataURLError, match='invalid address'):
                validate_saml_metadata_url('https://idp.example.com/metadata')


@patch('enterprise.api.v1.views.saml_utils.requests.get')
class TestFetchSAMLMetadataResponse(TestCase):
    """Tests for fetch_saml_metadata_response."""

    def setUp(self):
        super().setUp()
        dns_patch = mock_saml_metadata_dns()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)

    def test_returns_response_without_following_redirects_itself(self, mock_get):
        mock_get.return_value = _metadata_response()
        response = fetch_saml_metadata_response('https://idp.example.com/metadata')
        assert response.status_code == 200
        mock_get.assert_called_once_with(
            'https://idp.example.com/metadata', verify=True, timeout=30, allow_redirects=False,
        )

    def test_follows_valid_redirects(self, mock_get):
        mock_get.side_effect = [
            _metadata_response(302, '/v2/metadata'),
            _metadata_response(301, 'https://cdn.example.com/metadata.xml'),
            _metadata_response(),
        ]
        response = fetch_saml_metadata_response('https://idp.example.com/metadata')
        assert response.status_code == 200
        assert [call.args[0] for call in mock_get.call_args_list] == [
            'https://idp.example.com/metadata',
            'https://idp.example.com/v2/metadata',
            'https://cdn.example.com/metadata.xml',
        ]

    def test_redirect_to_unsafe_url_is_not_fetched(self, mock_get):
        for location in (
            'http://169.254.169.254/latest/meta-data/',
            'http://internal.example.com/',
            'https://169.254.169.254/latest/meta-data/',
            '//169.254.169.254/latest/meta-data/',
            'https://10.0.0.5/admin',
        ):
            mock_get.reset_mock()
            mock_get.side_effect = [_metadata_response(302, location)]
            with pytest.raises(SAMLMetadataURLError):
                fetch_saml_metadata_response('https://idp.example.com/metadata')
            assert mock_get.call_count == 1

    def test_redirect_to_hostname_resolving_to_internal_address_is_not_fetched(self, mock_get):
        mock_get.side_effect = [_metadata_response(302, 'https://imds.example.com/latest/meta-data/')]
        addresses = {'idp.example.com': '93.184.215.14', 'imds.example.com': '169.254.169.254'}

        def fake_getaddrinfo(host, port, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (addresses[host], port))]

        with patch('enterprise.api.v1.views.saml_utils.getaddrinfo', side_effect=fake_getaddrinfo):
            with pytest.raises(SAMLMetadataURLError, match='forbidden'):
                fetch_saml_metadata_response('https://idp.example.com/metadata')
        assert mock_get.call_count == 1

    def test_too_many_redirects(self, mock_get):
        mock_get.side_effect = [
            _metadata_response(302, f'https://idp.example.com/{hop}') for hop in range(SAML_METADATA_MAX_REDIRECTS + 1)
        ]
        with pytest.raises(SAMLMetadataURLError, match='redirected more than'):
            fetch_saml_metadata_response('https://idp.example.com/metadata')
        assert mock_get.call_count == SAML_METADATA_MAX_REDIRECTS + 1

    def test_fetch_metadata_xml_rejects_unsafe_redirect(self, mock_get):
        mock_get.side_effect = [_metadata_response(302, 'http://169.254.169.254/latest/meta-data/')]
        with pytest.raises(SAMLMetadataURLError, match='must use HTTPS'):
            fetch_metadata_xml('https://idp.example.com/metadata')
        assert mock_get.call_count == 1
