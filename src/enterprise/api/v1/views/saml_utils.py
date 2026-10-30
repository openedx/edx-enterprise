"""
Utility functions for SAML provider administration.

Migrated from openedx-platform's third_party_auth/utils.py since they are only
used by the SAML admin viewsets now hosted in edx-enterprise.
"""
import ipaddress
import logging
import socket
from socket import getaddrinfo
from urllib.parse import urljoin, urlparse
from uuid import UUID

import requests
from lxml import etree

from django.conf import settings

log = logging.getLogger(__name__)

# fetch_saml_metadata_response follows redirects itself so that it can validate
# each hop, so the limit requests applies when it follows them does not apply
# here and we need our own. This is the same number requests uses; it is more
# than any IdP needs, the point is only that there is a limit.
SAML_METADATA_MAX_REDIRECTS = 30

# Cloud instance metadata addresses that are not link-local, so the link-local
# check does not cover them. fd00:ec2::254 is the AWS metadata service over IPv6.
CLOUD_METADATA_IP_ADDRESSES = frozenset({
    ipaddress.ip_address('fd00:ec2::254'),
})


class SAMLMetadataURLError(Exception):
    """A SAML metadata URL failed security validation."""


def _check_saml_metadata_address(addr):
    """
    Raise SAMLMetadataURLError if a SAML metadata URL's IP address is not safe to fetch.
    """
    # An IPv4-mapped IPv6 address (::ffff:a.b.c.d) reaches the IPv4 address.
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    # Loopback, link-local, reserved, unspecified and multicast ranges are never
    # legitimate SAML IdP addresses regardless of deployment topology.
    if any([
        addr.is_loopback,
        addr.is_link_local,
        addr.is_reserved,
        addr.is_unspecified,
        addr.is_multicast,
        addr in CLOUD_METADATA_IP_ADDRESSES,
    ]):
        raise SAMLMetadataURLError(
            f"SAML metadata URL hostname is a forbidden IP address: {addr}"
        )

    if addr.is_global:
        return

    # Private ranges are blocked by default but can be allowed via Django settings
    # for deployments where the SAML IdP lives on the same private network.
    if addr.is_private:
        if settings.SAML_METADATA_URL_ALLOW_PRIVATE_IPS:
            return
        raise SAMLMetadataURLError(
            f"SAML metadata URL hostname is a private IP address: {addr}. "
            "Set SAML_METADATA_URL_ALLOW_PRIVATE_IPS = True in Django settings to allow this."
        )

    # Anything else (e.g. shared address space 100.64.0.0/10) is not publicly routable.
    raise SAMLMetadataURLError(
        f"SAML metadata URL hostname is not a publicly routable IP address: {addr}"
    )


def validate_saml_metadata_url(url):
    """
    Validate that a SAML metadata URL is safe to fetch.

    Enforces HTTPS and blocks requests to loopback, link-local, reserved,
    unspecified and multicast IP addresses, and to known cloud metadata
    addresses. Link-local specifically covers cloud instance metadata endpoints
    (169.254.0.0/16, e.g. the AWS metadata service at 169.254.169.254).
    Reserved addresses (e.g. 240.0.0.0/4) are IETF-assigned ranges that are
    never routable on real networks.

    Private IP ranges (RFC 1918: 10.x, 172.16.x, 192.168.x) are also blocked by
    default, since most Open edX deployments fetch SAML metadata from public IdPs.
    Operators running in a private network where the SAML IdP has a private IP can
    opt out by setting SAML_METADATA_URL_ALLOW_PRIVATE_IPS = True in Django settings.

    Hostnames are resolved and every address they resolve to is checked. The
    HTTP client resolves the hostname again when it connects, so a DNS record
    that changes between the two lookups is not caught here; because the URL
    must use HTTPS and certificates are verified, such a connection fails the
    TLS handshake. Operators are still encouraged to complement this with
    network-level egress filtering that blocks outbound connections from the
    Open edX server to link-local (169.254.0.0/16) and RFC 1918 private address
    ranges.

    This only checks one URL. Use fetch_saml_metadata_response to fetch, which
    also checks every redirect.

    Raises SAMLMetadataURLError if the URL fails validation.
    """
    parsed = urlparse(url)

    if parsed.scheme != 'https':
        raise SAMLMetadataURLError(
            f"SAML metadata URL must use HTTPS, got scheme: {parsed.scheme!r}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise SAMLMetadataURLError("SAML metadata URL has no hostname")

    try:
        addrs = [ipaddress.ip_address(hostname)]
    except ValueError:
        # hostname is a domain name, not a numeric IP literal; resolve it.
        addrs = _resolve_saml_metadata_hostname(hostname, parsed.port or 443)

    for addr in addrs:
        _check_saml_metadata_address(addr)


def _resolve_saml_metadata_hostname(hostname, port):
    """
    Resolve a SAML metadata URL's hostname to the list of IP addresses it points at.

    Raises SAMLMetadataURLError if the hostname does not resolve or resolves to
    something that is not an IP address.
    """
    try:
        addrinfo = getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as error:
        raise SAMLMetadataURLError(
            f"SAML metadata URL hostname could not be resolved: {hostname}"
        ) from error

    addrs = []
    for *_, sockaddr in addrinfo:
        # A link-local IPv6 result can carry a zone index ("fe80::1%eth0").
        # ipaddress accepts that, but an address with a zone compares unequal to
        # the same address without one, so "fd00:ec2::254%eth0" would get past
        # the CLOUD_METADATA_IP_ADDRESSES check. Strip the zone before checking.
        address = str(sockaddr[0]).split('%', 1)[0]
        try:
            addrs.append(ipaddress.ip_address(address))
        except ValueError as error:
            raise SAMLMetadataURLError(
                f"SAML metadata URL hostname resolved to an invalid address: {address!r}"
            ) from error
    return addrs


def fetch_saml_metadata_response(url):
    """
    Fetch a SAML metadata URL, validating it and every redirect it follows.

    Redirects are followed by hand so that each Location is checked with
    validate_saml_metadata_url before it is requested; this keeps a redirect
    from reaching a plain-HTTP or internal address.

    Raises SAMLMetadataURLError if any URL fails validation or there are too
    many redirects, and the requests exceptions for network errors. The caller
    checks the status of the returned response.
    """
    for _ in range(SAML_METADATA_MAX_REDIRECTS + 1):
        validate_saml_metadata_url(url)
        response = requests.get(url, verify=True, timeout=30, allow_redirects=False)
        if not response.is_redirect:
            return response
        location = response.headers['Location']
        response.close()
        url = urljoin(url, location)

    raise SAMLMetadataURLError(
        f"SAML metadata URL redirected more than {SAML_METADATA_MAX_REDIRECTS} times"
    )


def validate_uuid4_string(uuid_string):
    """
    Returns True if valid uuid4 string, or False
    """
    try:
        UUID(uuid_string, version=4)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def convert_saml_slug_provider_id(provider):
    """
    Provider id is stored with the backend type prefixed to it (ie "saml-")
    Slug is stored without this prefix.
    This just converts between them whenever you expect the opposite of what you currently have.

    Arguments:
        provider (string): provider_id or slug

    Returns:
        (string): Opposite of what you inputted (slug -> provider_id; provider_id -> slug)
    """
    if provider.startswith('saml-'):
        return provider[5:]
    else:
        return 'saml-' + provider


def fetch_metadata_xml(url):
    """
    Fetches IDP metadata from provider url
    Returns: xml document
    """
    try:
        log.info("Fetching %s", url)
        # Validates the URL and every redirect. May raise SAMLMetadataURLError, SSLError or ConnectionError
        response = fetch_saml_metadata_response(url)
        response.raise_for_status()  # May raise an HTTPError

        try:
            parser = etree.XMLParser(remove_comments=True)
            xml = etree.fromstring(response.content, parser)
        except etree.XMLSyntaxError:  # lint-amnesty, pylint: disable=try-except-raise
            raise
        return xml
    except (requests.exceptions.SSLError, requests.exceptions.HTTPError, requests.exceptions.RequestException) as error:
        log.exception(str(error), exc_info=error)
        raise
    except etree.XMLSyntaxError as error:
        log.exception(str(error), exc_info=error)
        raise
