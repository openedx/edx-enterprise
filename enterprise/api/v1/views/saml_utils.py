"""
Utility functions for SAML provider administration.

Migrated from openedx-platform's third_party_auth/utils.py since they are only
used by the SAML admin viewsets now hosted in edx-enterprise.
"""
import ipaddress
import logging
from urllib.parse import urlparse
from uuid import UUID

import requests
from django.conf import settings
from lxml import etree

log = logging.getLogger(__name__)


class SAMLMetadataURLError(Exception):
    """A SAML metadata URL failed security validation."""


def validate_saml_metadata_url(url):
    """
    Validate that a SAML metadata URL is safe to fetch.

    Enforces HTTPS and blocks requests to loopback, link-local, and reserved IP
    addresses. Link-local specifically covers cloud instance metadata endpoints
    (169.254.0.0/16, e.g. the AWS metadata service at 169.254.169.254).
    Reserved addresses (e.g. 240.0.0.0/4) are IETF-assigned ranges that are
    never routable on real networks.

    Private IP ranges (RFC 1918: 10.x, 172.16.x, 192.168.x) are also blocked by
    default, since most Open edX deployments fetch SAML metadata from public IdPs.
    Operators running in a private network where the SAML IdP has a private IP can
    opt out by setting SAML_METADATA_URL_ALLOW_PRIVATE_IPS = True in Django settings.

    Limitation: IP address checks only apply to literal IPs in the URL. Hostname-
    based URLs are not validated against the IP blocklists. Operators are encouraged
    to complement this with network-level egress filtering that blocks outbound
    connections from the Open edX server to link-local (169.254.0.0/16) and RFC
    1918 private address ranges.

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
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # hostname is a domain name, not a numeric IP literal — pass through.
        return

    # Loopback, link-local, and reserved ranges are never legitimate SAML IdP
    # addresses regardless of deployment topology.
    if addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise SAMLMetadataURLError(
            f"SAML metadata URL hostname is a forbidden IP address: {addr}"
        )

    # Private ranges are blocked by default but can be allowed via Django settings
    # for deployments where the SAML IdP lives on the same private network.
    if addr.is_private and not settings.SAML_METADATA_URL_ALLOW_PRIVATE_IPS:
        raise SAMLMetadataURLError(
            f"SAML metadata URL hostname is a private IP address: {addr}. "
            "Set SAML_METADATA_URL_ALLOW_PRIVATE_IPS = True in Django settings to allow this."
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
        validate_saml_metadata_url(url)
        log.info("Fetching %s", url)
        response = requests.get(url, verify=True, timeout=30)  # May raise HTTPError or SSLError or ConnectionError
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
