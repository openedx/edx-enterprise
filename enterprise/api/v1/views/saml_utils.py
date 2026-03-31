"""
Utility functions for SAML provider administration.

Migrated from openedx-platform's third_party_auth/utils.py since they are only
used by the SAML admin viewsets now hosted in edx-enterprise.
"""
import logging
from uuid import UUID

import requests
from lxml import etree

log = logging.getLogger(__name__)


def validate_uuid4_string(uuid_string):
    """
    Returns True if valid uuid4 string, or False
    """
    try:
        UUID(uuid_string, version=4)
    except ValueError:
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
        if not url.lower().startswith('https'):
            log.warning("This SAML metadata URL is not secure! It should use HTTPS. (%s)", url)
        response = requests.get(url, verify=True)  # May raise HTTPError or SSLError or ConnectionError
        response.raise_for_status()  # May raise an HTTPError

        try:
            parser = etree.XMLParser(remove_comments=True)
            xml = etree.fromstring(response.content, parser)
        except etree.XMLSyntaxError:  # lint-amnesty, pylint: disable=try-except-raise
            raise
        return xml
    except (requests.exceptions.SSLError, requests.exceptions.HTTPError, requests.exceptions.RequestException) as error:
        log.exception(str(error), exc_info=error)
        raise error
    except etree.XMLSyntaxError as error:
        log.exception(str(error), exc_info=error)
        raise error
